import pytest

from app.core.db import q1
from app.llm.client import LLMClient
from app.llm.providers import MockChat
from app.services import planner
from tests.integration.test_platform import ids as member_ids
from tests.support.planning import approved_spec, plan_reply, proposed_plan


def test_plan_needs_an_approved_spec(api, room):
    with pytest.raises(planner.PlanError):
        planner.generate(room, LLMClient(MockChat(["{}"]), room))


def test_generate_stores_proposed_tasks_owners_and_contracts(api, room):
    proposed_plan(room)
    tasks = {t["key"]: t for t in planner.tasks(room)}

    assert set(tasks) == {"db", "api", "ui"} and all(
        t["status"] == "proposed" for t in tasks.values()
    )
    assert tasks["api"]["owner_member_id"] == member_ids(api, room)["aman"]
    assert {c["name"]: c["status"] for c in planner.contracts(room)} == {
        "db": "proposed",
        "shop-api": "proposed",
    }


def test_cycle_is_rejected(api, room):
    ids = approved_spec(room)
    with pytest.raises(planner.PlanError, match="cycle"):
        planner.generate(room, LLMClient(MockChat([plan_reply(ids, cycle=True)]), room))
    assert planner.tasks(room) == []


def test_check_acyclic_unit():
    assert planner.check_acyclic({"a": [], "b": ["a"]}) == ["a", "b"]
    with pytest.raises(planner.PlanError):
        planner.check_acyclic({"a": ["b"], "b": ["a"]})
    with pytest.raises(planner.PlanError):
        planner.check_acyclic({"a": ["ghost"]})


def test_tasks_cannot_start_until_plan_and_contracts_are_approved(api, room):
    proposed_plan(room)
    api_task = next(t for t in planner.tasks(room) if t["key"] == "api")
    assert planner.can_start(api_task["id"])[0] is False

    planner.approve(room)

    assert planner.can_start(api_task["id"]) == (True, "")
    assert all(c["status"] == "approved" for c in planner.contracts(room))


def test_editing_a_task_keeps_the_graph_acyclic(api, room):
    proposed_plan(room)
    db = next(t for t in planner.tasks(room) if t["key"] == "db")
    with pytest.raises(planner.PlanError):
        planner.update_task(db["id"], {"depends_on": ["ui"]})
    riya = member_ids(api, room)["riya"]
    assert planner.update_task(db["id"], {"owner_member_id": riya})["owner_member_id"] == riya


def test_approved_plans_are_fixed(api, room):
    proposed_plan(room)
    planner.approve(room)
    t = planner.tasks(room)[0]
    with pytest.raises(planner.PlanError):
        planner.update_task(t["id"], {"title": "x"})


def test_contracts_are_versioned_and_tasks_stay_pinned(api, room):
    proposed_plan(room)
    planner.approve(room)
    v1 = q1("SELECT id FROM contracts WHERE room_id=? AND name='shop-api' AND version=1", (room,))[
        "id"
    ]

    v2 = planner.propose_contract_version(room, "shop-api", "api", '{"paths": {}}', None)
    assert v2["version"] == 2 and v2["status"] == "proposed"
    planner.approve_contract(v2["id"])

    assert q1("SELECT status FROM contracts WHERE id=?", (v1,))["status"] == "superseded"
    ui = next(t for t in planner.tasks(room) if t["key"] == "ui")
    assert v1 in ui["contract_ids"]  # pinned to the version approved with the plan
