"""Blank projects: the first planned task builds the first version (the bootstrap) instead of
failing with "no approved baseline", and a waiting first build blocks a second one."""

import pytest

from app.core.db import ex, now, q1
from app.routers import rooms
from app.services import orchestrator, planner
from tests.support.planning import proposed_plan


@pytest.fixture()
def blank(api):
    return api.post(
        "/api/rooms",
        json={"name": "blank-plan", "template": "blank", "members": [{"name": "riya"}]},
    ).json()["id"]


@pytest.fixture()
def started(monkeypatch):
    calls = []
    monkeypatch.setattr(
        rooms, "_start", lambda *a, **k: calls.append(a) or {"accepted": True, "agent": a[1]}
    )
    return calls


def _first_task(rid):
    proposed_plan(rid)
    planner.approve(rid)
    return planner.tasks(rid)[0]


def _riya(rid):
    return q1("SELECT id FROM members WHERE room_id=? AND name='riya'", (rid,))["id"]


def test_first_planned_task_in_a_blank_project_runs_as_the_bootstrap(api, blank, started):
    t = _first_task(blank)
    agent = api.get(f"/api/rooms/{blank}/catalog").json()[0]["key"]

    r = api.post(f"/api/tasks/{t['id']}/start", json={"member_id": _riya(blank), "agent": agent})

    assert r.status_code == 200, r.text
    rid, _name, text, _role, boot, _wait, task_id, context_md = started[0]
    assert rid == blank and boot is True and task_id == t["id"]
    assert text.startswith("This project is empty") and t["title"] in text
    assert context_md  # the confirmed spec travels with the first build


def test_a_waiting_first_build_blocks_starting_another_task(api, blank, started):
    t = _first_task(blank)
    agent = api.get(f"/api/rooms/{blank}/catalog").json()[0]["key"]
    ex(
        "INSERT INTO changes(room_id,agent,member_id,branch,summary,status,created,kind) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (blank, "riya-agent", _riya(blank), "b", "first", "bootstrap_review", now(), "bootstrap"),
    )

    r = api.post(f"/api/tasks/{t['id']}/start", json={"member_id": _riya(blank), "agent": agent})

    assert r.status_code == 409 and "waiting for review" in r.json()["detail"]
    assert not started


def test_after_approval_tasks_run_normally(api, blank, started):
    t = _first_task(blank)
    ex("UPDATE rooms SET bootstrapped=1 WHERE id=?", (blank,))
    agent = api.get(f"/api/rooms/{blank}/catalog").json()[0]["key"]

    api.post(f"/api/tasks/{t['id']}/start", json={"member_id": _riya(blank), "agent": agent})

    assert started[0][4] is False and not started[0][2].startswith("This project is empty")


def test_edit_scope_never_rejects_a_first_build(api, blank):
    ex("UPDATE rooms SET edit_scope='task' WHERE id=?", (blank,))
    ch = {"task_id": 1, "kind": "bootstrap"}
    assert orchestrator._scope_violations(blank, ch, ["app/main.py", "protected/tests/t.py"]) == []


def test_with_no_claude_key_the_run_uses_a_ready_free_model(api, blank, started, monkeypatch):
    from app.core import config

    monkeypatch.setattr(config, "FREE_PROVIDER_KEYS", {"gemini": "AQ.demo"})
    t = _first_task(blank)

    api.post(f"/api/tasks/{t['id']}/start", json={"member_id": _riya(blank), "agent": "builder"})

    model = q1("SELECT model FROM agents WHERE room_id=? AND name='riya-agent'", (blank,))["model"]
    assert model.startswith("gemini:")
