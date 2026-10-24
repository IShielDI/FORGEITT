"""Stage 23: the sample todo app end to end, with mock providers only.

create workspace -> chat -> observer proposes -> humans confirm the spec -> planner proposes ->
owner approves the plan -> two agents work in parallel (one plants a bug) -> mirror checks ->
the hidden test catches the bug and the failure is routed to its owner -> fix -> re-run -> a human
approves the merge (release tag) -> tasks are done.
"""

import json

import pytest

from app.core import config
from app.core.db import q1
from app.llm import client as llm
from app.llm.providers import MockChat
from app.services import agent_runner, gitops, ledger
from tests.support import todo_scenarios


def _with_mock(*replies):
    llm.use_provider(MockChat(list(replies)))


@pytest.fixture()
def fake_agents(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_UNSAFE_SANDBOX", True)
    monkeypatch.setattr(config, "AGENT_SANDBOX", "subprocess")

    def use(plan):
        monkeypatch.setattr(agent_runner, "AnthropicProvider", lambda key, model: plan)

    return use


def test_todo_app_demo_flow(api, fake_agents):
    # 1. workspace from the todo sample; fast profile (build, locked + hidden tests); humans approve
    room = api.post(
        "/api/rooms",
        json={
            "name": "Todo team",
            "template": "todo",
            "members": [{"name": "riya", "contribution": 5}, {"name": "aman", "contribution": 5}],
        },
    ).json()
    rid, members = room["id"], {m["name"]: m["id"] for m in room["members"]}
    for mid in members.values():
        ledger.add_key(mid, "anthropic", "plain", "sk-ant-demo-0000")
    assert api.put(f"/api/rooms/{rid}/profile", json={"profile": "fast"}).status_code == 200

    # 2. chat, and the observer proposes spec items from it
    ids = [
        api.post(
            f"/api/rooms/{rid}/messages", json={"body": text, "member_id": members[who]}
        ).json()["id"]
        for who, text in (
            ("riya", "The heading should say Team todos."),
            ("aman", "Agreed. And listing must stay fast."),
            ("riya", "Yes, let's make listing faster."),
        )
    ]
    observed = {
        "items": [
            {
                "kind": "requirement",
                "text": "The page heading says Team todos",
                "source_message_ids": [ids[0]],
                "confidence": 0.8,
            },
            {
                "kind": "decision",
                "text": "Make the todo listing faster",
                "source_message_ids": [ids[1], ids[2]],
                "confidence": 0.85,
            },
        ]
    }
    _with_mock(json.dumps(observed))
    try:
        assert len(api.post(f"/api/rooms/{rid}/observe").json()["created"]) == 2
    finally:
        llm.use_provider(None)

    # 3. humans confirm the spec
    items = api.get(f"/api/rooms/{rid}/spec").json()["items"]
    assert all(i["status"] == "proposed" for i in items)  # nothing confirmed by the agent
    for i in items:
        assert api.post(f"/api/spec/items/{i['id']}/confirm").status_code == 200
    by_text = {i["text"]: i["id"] for i in items}

    # 4. planner proposes, owner approves (contracts pinned)
    plan = {
        "contracts": [
            {
                "kind": "api",
                "name": "todo-api",
                "content": json.dumps(
                    {"paths": {"/api/todos": {"get": {}}, "/todos": {"post": {}}}}
                ),
                "spec_item_ids": [by_text["Make the todo listing faster"]],
            }
        ],
        "tasks": [
            {
                "key": "ui",
                "title": "Rename the heading",
                "component": "frontend",
                "suggested_owner": "riya",
                "spec_item_ids": [by_text["The page heading says Team todos"]],
                "contracts": ["todo-api"],
            },
            {
                "key": "api",
                "title": "Faster listing",
                "component": "backend",
                "suggested_owner": "aman",
                "spec_item_ids": [by_text["Make the todo listing faster"]],
                "contracts": ["todo-api"],
            },
        ],
    }
    _with_mock(json.dumps(plan))
    try:
        assert api.post(f"/api/rooms/{rid}/plan/generate").status_code == 200
    finally:
        llm.use_provider(None)
    tasks = {t["key"]: t["id"] for t in api.post(f"/api/rooms/{rid}/plan/approve").json()["tasks"]}

    # 5. two agents work in their own clones; the api agent plants a bug the visible tests miss
    fake_agents(todo_scenarios.ui_heading())
    ui = api.post(
        f"/api/tasks/{tasks['ui']}/start",
        params={"wait": "true"},
        json={"member_id": members["riya"]},
    ).json()
    assert ui["change"]["status"] == "passed"
    fake_agents(todo_scenarios.api_speedup_with_bug())
    bug = api.post(
        f"/api/tasks/{tasks['api']}/start",
        params={"wait": "true"},
        json={"member_id": members["aman"]},
    ).json()

    # 6. the hidden test catches it; the failure is routed (with confidence) to the backend owner
    assert bug["change"]["status"] == "tests_failed"
    ev = json.loads(q1("SELECT evidence FROM changes WHERE id=?", (bug["change_id"],))["evidence"])
    failing = [t["name"] for t in ev["tests"]["tests"] if not t["passed"]]
    assert any("done_flag" in n for n in failing) and all(
        t["passed"] for t in ev["tests"]["tests"] if not t["hidden"]
    )
    assert (
        ev["routed"]["part"] == "backend"
        and ev["routed"]["assigned_to"] == "aman"
        and ev["routed"]["confidence"] < 1
    )
    assert (
        api.post(f"/api/rooms/{rid}/approve", json={"change_ids": [bug["change_id"]]}).status_code
        == 400
    )

    # 7. the owner fixes it; the new run passes
    fake_agents(todo_scenarios.api_fix())
    fix = api.post(
        f"/api/tasks/{tasks['api']}/start",
        params={"wait": "true"},
        json={"member_id": members["aman"]},
    ).json()
    assert fix["change"]["status"] == "passed"

    # 8. a human approves; the merge service merges and tags a release
    merged = api.post(
        f"/api/rooms/{rid}/approve", json={"change_ids": [ui["change_id"], fix["change_id"]]}
    ).json()
    assert merged["release"] == "release/1"
    main = gitops.git(gitops.original(rid), "show", "main:app/main.py").stdout
    assert "Team todos" in main and "0 AS done" not in main
    assert {t["status"] for t in api.get(f"/api/rooms/{rid}/plan").json()["tasks"]} == {"done"}
    # the task traces back to the requirement it implements
    assert api.get(f"/api/tasks/{tasks['ui']}/trace").json()["requirement"] == [
        by_text["The page heading says Team todos"]
    ]
