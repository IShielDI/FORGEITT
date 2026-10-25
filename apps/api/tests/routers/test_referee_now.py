"""Run the referee for one change now, instead of waiting for a batch of changes."""

import threading

import pytest

from app.core.db import ex, now, q1
from app.services import orchestrator


def _change(room, status, verdict=None):
    return ex(
        "INSERT INTO changes(room_id,agent,branch,summary,status,verdict,created) "
        "VALUES(?,?,?,?,?,?,?)",
        (room, "riya-agent", "agent/riya-agent", "test", status, verdict, now()),
    )


@pytest.fixture()
def ran(monkeypatch):
    calls = []
    done = threading.Event()

    def fake(room, force=False):
        calls.append((room, force))
        done.set()

    monkeypatch.setattr(orchestrator, "run_referee", fake)
    return calls, done


def test_fast_workspaces_say_to_switch_the_checking_level(api, room, ran):
    ex("UPDATE rooms SET verification_profile='fast' WHERE id=?", (room,))
    cid = _change(room, "ready")
    r = api.post(f"/api/changes/{cid}/referee")
    assert r.status_code == 409 and "Standard or Strict" in r.json()["detail"]


def test_a_tests_only_change_is_queued_again_and_the_referee_starts(api, room, ran):
    calls, done = ran
    ex("UPDATE rooms SET verification_profile='standard' WHERE id=?", (room,))
    cid = _change(room, "passed", "tests_only")

    r = api.post(f"/api/changes/{cid}/referee")

    assert r.json() == {"started": True}
    assert done.wait(5) and calls == [(room, True)]
    assert q1("SELECT status FROM changes WHERE id=?", (cid,))["status"] == "ready"


def test_merged_changes_and_busy_referees_are_refused(api, room, ran):
    ex("UPDATE rooms SET verification_profile='standard' WHERE id=?", (room,))
    merged = _change(room, "merged")
    assert api.post(f"/api/changes/{merged}/referee").status_code == 409

    _change(room, "referee")  # one is being checked right now
    waiting = _change(room, "ready")
    r = api.post(f"/api/changes/{waiting}/referee")
    assert r.status_code == 409 and "already checking" in r.json()["detail"]


def test_a_referee_service_error_can_be_retried_but_a_real_app_failure_cannot(api, room, ran):
    ex("UPDATE rooms SET verification_profile='standard' WHERE id=?", (room,))
    glitch = _change(room, "referee_failed", "service_error")
    assert api.post(f"/api/changes/{glitch}/referee").json() == {"started": True}
    assert q1("SELECT status FROM changes WHERE id=?", (glitch,))["status"] == "ready"

    ex("UPDATE changes SET status='merged' WHERE id=?", (glitch,))  # clear the queue
    broken = _change(room, "referee_failed", "app_failure")
    assert api.post(f"/api/changes/{broken}/referee").status_code == 409
