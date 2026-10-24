from app.services import knowledge, planner
from tests.support.planning import proposed_plan


def test_link_is_idempotent_and_traceable(api, room):
    a = knowledge.link(room, "requirement", 1, "task", 2, "implemented_by", created_by=7)
    b = knowledge.link(room, "requirement", 1, "task", 2, "implemented_by")
    assert a == b
    row = knowledge.links(room)[0]
    assert row["created_by"] == 7 and row["created"] and row["version"] == 1


def test_traversal_respects_depth(api, room):
    knowledge.link(room, "decision", 1, "contract", 2, "specifies")
    knowledge.link(room, "contract", 2, "task", 3, "constrains")

    assert {r["src_type"] for r in knowledge.traverse(room, "task", 3, "back", depth=1)} == {
        "contract"
    }
    assert {r["src_type"] for r in knowledge.traverse(room, "task", 3, "back", depth=2)} == {
        "contract",
        "decision",
    }
    assert [r["dst_type"] for r in knowledge.traverse(room, "decision", 1, "forward", 5)] == [
        "contract",
        "task",
    ]


def test_plan_approval_links_tasks_back_to_requirements_and_decisions(api, room):
    ids = proposed_plan(room)
    planner.approve(room)
    tasks = {t["key"]: t["id"] for t in planner.tasks(room)}

    api_trace = knowledge.trace_task(room, tasks["api"])
    assert ids["login"] in api_trace["requirement"]
    assert ids["sqlite"] in api_trace["decision"]  # via the db contract it is pinned to
    ui_trace = knowledge.trace_task(room, tasks["ui"])
    assert ui_trace["requirement"] == [ids["cart"]]
