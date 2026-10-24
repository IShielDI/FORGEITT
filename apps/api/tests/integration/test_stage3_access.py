"""Logins, connecting a key, the agent catalog, picking an agent, live progress, stop."""

import json

import pytest

from app.core import config, db
from app.core.db import q, q1
from app.services import agent_runner
from tests.support.plans import bootstrap_plan
from tests.support.scripted import ScriptedProvider

FAKE_KEY = "sk-ant-api03-SECRETSECRETSECRET1234"


@pytest.fixture()
def team(api, monkeypatch):
    """A blank workspace of two people with logins switched ON."""
    monkeypatch.setattr(config, "REQUIRE_AUTH", True)
    r = api.post(
        "/api/rooms",
        json={
            "name": "auth",
            "template": "blank",
            "members": [{"name": "riya", "contribution": 5}, {"name": "aman", "contribution": 5}],
        },
    ).json()
    t = {
        m["name"]: {"H": {"Authorization": f"Bearer {m['token']}"}, "id": m["id"]}
        for m in r["members"]
    }
    return r["id"], t


def test_logins_are_required_and_scoped_to_the_room(api, team):
    rid, t = team
    assert api.get(f"/api/rooms/{rid}").status_code == 401
    assert api.get(f"/api/rooms/{rid}", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert api.get(f"/api/rooms/{rid}", headers=t["riya"]["H"]).status_code == 200
    other, t2 = None, None
    r2 = api.post("/api/rooms", json={"name": "other", "members": [{"name": "zed"}]}).json()
    assert (
        api.get(
            f"/api/rooms/{rid}", headers={"Authorization": f"Bearer {r2['members'][0]['token']}"}
        ).status_code
        == 401
    )  # another room's token
    assert api.get("/api/rooms").json() == []  # no room listing


def test_you_can_only_act_as_yourself(api, team):
    rid, t = team
    assert (
        api.get(
            f"/api/rooms/{rid}/budget", params={"member": t["aman"]["id"]}, headers=t["riya"]["H"]
        ).status_code
        == 403
    )
    assert (
        api.post(
            f"/api/rooms/{rid}/contribute",
            json={"amount": 5, "member_id": t["aman"]["id"]},
            headers=t["riya"]["H"],
        ).status_code
        == 403
    )
    assert api.get(f"/api/rooms/{rid}/budget", headers=t["riya"]["H"]).status_code == 200


def test_tokens_are_stored_hashed(api, team):
    rid, t = team
    row = q1("SELECT token_hash FROM members WHERE id=?", (t["riya"]["id"],))
    assert (
        len(row["token_hash"]) == 64
        and t["riya"]["H"]["Authorization"][7:] not in row["token_hash"]
    )


def test_connect_key_is_encrypted_and_never_echoed(api, team):
    rid, t = team
    H = t["riya"]["H"]
    assert (
        api.post(f"/api/rooms/{rid}/me/key", json={"anthropic_key": "hello"}, headers=H).status_code
        == 400
    )
    r = api.post(f"/api/rooms/{rid}/me/key", json={"anthropic_key": FAKE_KEY}, headers=H)
    assert r.status_code == 200 and FAKE_KEY not in r.text
    me = api.get(f"/api/rooms/{rid}/me", headers=H)
    assert me.json()["has_key"] and me.json()["key_last4"] == "1234" and FAKE_KEY not in me.text
    assert FAKE_KEY not in json.dumps(q("SELECT * FROM keys"))  # encrypted at rest
    assert FAKE_KEY not in api.get(f"/api/rooms/{rid}", headers=H).text
    assert api.get(f"/api/rooms/{rid}/me", headers=t["aman"]["H"]).json()["has_key"] is False


def test_catalog_is_editable_by_the_owner_only(api, team):
    rid, t = team
    cat = api.get(f"/api/rooms/{rid}/catalog", headers=t["aman"]["H"]).json()
    assert {"builder", "fixer"} <= {c["key"] for c in cat}
    body = {
        "key": "reviewer",
        "label": "Reviewer",
        "role_prompt": "Review only.",
        "model": "claude-haiku-5-5",
    }
    assert (
        api.put(f"/api/rooms/{rid}/catalog", json=body, headers=t["aman"]["H"]).status_code == 403
    )
    assert (
        api.put(f"/api/rooms/{rid}/catalog", json=body, headers=t["riya"]["H"]).status_code == 200
    )
    assert (
        api.put(
            f"/api/rooms/{rid}/catalog", json={**body, "model": "gpt-9"}, headers=t["riya"]["H"]
        ).status_code
        == 400
    )  # unpriced model refused
    assert any(
        c["key"] == "reviewer"
        for c in api.get(f"/api/rooms/{rid}/catalog", headers=t["aman"]["H"]).json()
    )


def test_hidden_tests_and_journey_are_owner_only(api, team):
    rid, t = team
    hid = {"filename": "test_x.py", "content": "def test_x(): pass\n"}
    assert (
        api.post(f"/api/rooms/{rid}/holdout", json=hid, headers=t["aman"]["H"]).status_code == 403
    )
    assert (
        api.post(f"/api/rooms/{rid}/holdout", json=hid, headers=t["riya"]["H"]).status_code == 200
    )
    assert (
        api.put(f"/api/rooms/{rid}/journey", json={"goal": "x"}, headers=t["aman"]["H"]).status_code
        == 403
    )


def _fake_model(monkeypatch, plan):
    monkeypatch.setattr(agent_runner, "AnthropicProvider", lambda key, model: plan)
    monkeypatch.setattr(config, "ALLOW_UNSAFE_SANDBOX", True)
    monkeypatch.setattr(config, "AGENT_SANDBOX", "subprocess")


def test_pick_an_agent_and_watch_it_work(api, team, monkeypatch):
    rid, t = team
    H = t["riya"]["H"]
    api.post(f"/api/rooms/{rid}/me/key", json={"anthropic_key": FAKE_KEY}, headers=H)
    _fake_model(monkeypatch, bootstrap_plan())
    r = api.post(
        f"/api/rooms/{rid}/run",
        params={"wait": "true"},
        json={"agent": "builder", "task": "Build a hello service"},
        headers=H,
    ).json()
    assert (
        r["status"] == "done" and r["change"]["status"] == "bootstrap_review"
    )  # first task in a blank project = bootstrap
    ev = api.get(f"/api/rooms/{rid}/events/list", headers=H).json()
    kinds = [e["kind"] for e in ev]
    assert (
        kinds[0] == "started" and "step" in kinds and "result" in kinds and kinds[-1] == "finished"
    )
    assert FAKE_KEY not in json.dumps(ev) and ev[0]["data"]["role"] == "builder"
    assert (
        api.get(f"/api/rooms/{rid}/events/list", params={"after": ev[-1]["id"]}, headers=H).json()
        == []
    )  # resume after the last id
    assert api.get(f"/api/rooms/{rid}/events/list", headers=t["aman"]["H"]).status_code == 200


def test_cannot_run_someone_elses_agent_or_two_tasks_at_once(api, team, monkeypatch):
    rid, t = team
    assert (
        api.post(
            f"/api/rooms/{rid}/agents/aman-agent/run", json={"task": "x"}, headers=t["riya"]["H"]
        ).status_code
        == 403
    )
    ag = q1("SELECT * FROM agents WHERE room_id=? AND name='riya-agent'", (rid,))
    db.ex("UPDATE agents SET status='running' WHERE id=?", (ag["id"],))
    r = api.post(
        f"/api/rooms/{rid}/bootstrap",
        json={"task": "x", "agent": "riya-agent"},
        headers=t["riya"]["H"],
        params={"wait": "false"},
    )
    assert r.status_code == 409


def test_real_model_without_a_sandbox_is_refused_and_says_so(api, team, monkeypatch):
    rid, t = team
    H = t["riya"]["H"]
    monkeypatch.setattr(config, "ALLOW_UNSAFE_SANDBOX", False)
    monkeypatch.setattr(config, "AGENT_SANDBOX", "auto")
    monkeypatch.setattr(agent_runner, "_docker_ok", False)
    r = api.post(
        f"/api/rooms/{rid}/run",
        params={"wait": "true"},
        json={"agent": "builder", "task": "x"},
        headers=H,
    ).json()
    assert r["status"] == "error" and "Refused" in r["final_text"]
    assert [e["kind"] for e in api.get(f"/api/rooms/{rid}/events/list", headers=H).json()][
        -1
    ] == "finished"


def test_stop_ends_the_run_without_a_change(api, team, monkeypatch):
    rid, t = team
    H = t["riya"]["H"]
    api.post(f"/api/rooms/{rid}/me/key", json={"anthropic_key": FAKE_KEY}, headers=H)

    class Stopper(ScriptedProvider):
        def complete(self, *a):
            r = super().complete(*a)
            if self.i == 1:
                api.post(f"/api/rooms/{rid}/agents/riya-agent/stop", headers=H)
            return r

    plan = Stopper(
        [
            [("tool", "bash", {"command": "ls"})],
            [("tool", "bash", {"command": "ls"})],
            [("text", "done")],
        ]
    )
    _fake_model(monkeypatch, plan)
    r = api.post(
        f"/api/rooms/{rid}/run",
        params={"wait": "true"},
        json={"agent": "builder", "task": "x"},
        headers=H,
    ).json()
    assert r["status"] == "stopped" and r["change_id"] is None and plan.i == 1
    assert (
        q1("SELECT status FROM agents WHERE name='riya-agent' AND room_id=?", (rid,))["status"]
        == "stopped"
    )


def test_cors_is_not_wildcard():
    assert "*" not in config.CORS_ORIGINS
