"""Stages 13-14: start a planned task in its own clone, context file, submission and handoff."""

import json

import pytest

from app.core import config
from app.core.db import q1
from app.llm import client as llm
from app.llm.providers import MockChat
from app.services import agent_runner, gitops, handoff, knowledge, ledger, planner
from tests.integration.test_platform import ids
from tests.support.planning import proposed_plan
from tests.support.scripted import ScriptedProvider

E = "str_replace_based_edit_tool"


def _edit_plan():
    return ScriptedProvider(
        [
            [("tool", E, {"command": "view", "path": "TASK_CONTEXT.md"})],
            [("tool", E, {"command": "create", "path": "app/notes.py", "file_text": "NOTE = 1\n"})],
            [("text", "Handoff: added app/notes.py")],
        ]
    )


@pytest.fixture()
def fake_model(monkeypatch):
    plan = _edit_plan()
    monkeypatch.setattr(agent_runner, "AnthropicProvider", lambda key, model: plan)
    monkeypatch.setattr(config, "ALLOW_UNSAFE_SANDBOX", True)
    monkeypatch.setattr(config, "AGENT_SANDBOX", "subprocess")
    return plan


def _task(room, key="api"):
    return next(t for t in planner.tasks(room) if t["key"] == key)


def test_cannot_start_before_the_plan_is_approved(api, room):
    proposed_plan(room)
    r = api.post(
        f"/api/tasks/{_task(room)['id']}/start", json={"member_id": ids(api, room)["aman"]}
    )
    assert r.status_code == 409


def test_start_runs_in_own_clone_with_context_and_links_the_change(api, room, fake_model):
    proposed_plan(room)
    planner.approve(room)
    aman = ids(api, room)["aman"]
    ledger.add_key(aman, "anthropic", "plain", "sk-ant-test-0000")
    t = _task(room)
    llm.use_provider(
        MockChat([json.dumps({"what_changed": ["Added app/notes.py"], "how_to_test": ["pytest"]})])
    )
    try:
        r = api.post(
            f"/api/tasks/{t['id']}/start", params={"wait": "true"}, json={"member_id": aman}
        ).json()
    finally:
        llm.use_provider(None)

    assert r["status"] == "done" and r["change_id"]
    ch = q1("SELECT * FROM changes WHERE id=?", (r["change_id"],))
    assert ch["task_id"] == t["id"] and len(ch["commit_sha"]) == 40
    ws = gitops.room_dir(room) / "workspaces" / "aman-agent"
    assert "Task api" in (ws / "TASK_CONTEXT.md").read_text()  # the agent read its context pack
    changed = gitops.git(
        gitops.original(room), "diff", "--name-only", f"main...{ch['branch']}"
    ).stdout
    assert (
        "app/notes.py" in changed and "TASK_CONTEXT.md" not in changed
    )  # never part of the change
    summary = json.loads(ch["handoff"])
    assert summary["source"] == "diff" and summary["what_changed"] == ["Added app/notes.py"]
    assert planner.task(t["id"])["status"] == "submitted"
    assert any(lk["relation"] == "produced" for lk in knowledge.links(room))


def test_only_the_task_owner_or_workspace_owner_may_start(api, room, fake_model):
    proposed_plan(room)
    planner.approve(room)
    t = _task(room)  # suggested owner: aman
    r = api.post(f"/api/tasks/{t['id']}/start", json={"member_id": ids(api, room)["kriti"]})
    assert r.status_code == 403


def test_wall_clock_limit_pauses_the_run(api, room, fake_model, monkeypatch):
    monkeypatch.setattr(config, "AGENT_TIME_LIMIT_S", -1)
    riya = ids(api, room)["riya"]
    ledger.add_key(riya, "anthropic", "plain", "sk-ant-test-0000")
    res = agent_runner.run_task(room, "riya-agent", "anything")
    assert res["status"] == "paused_time" and res["change_id"] is None


def test_handoff_falls_back_to_the_agent_note_and_says_so(api, room, fake_model):
    riya = ids(api, room)["riya"]
    ledger.add_key(riya, "anthropic", "plain", "sk-ant-test-0000")
    res = agent_runner.run_task(room, "riya-agent", "add notes", summary="notes")
    llm.use_provider(MockChat(["not json", "still not json"]))
    try:
        summary = handoff.generate(res["change_id"], "I added notes")
    finally:
        llm.use_provider(None)
    assert summary["source"] == "agent_note" and summary["what_changed"] == ["I added notes"]


def test_submit_without_a_change_is_a_409(api, room):
    proposed_plan(room)
    planner.approve(room)
    assert api.post(f"/api/tasks/{_task(room)['id']}/submit").status_code == 409
