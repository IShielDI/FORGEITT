from app.services import context, planner
from tests.support.planning import proposed_plan


def _approved(api, room):
    ids = proposed_plan(room)
    planner.approve(room)
    return ids, {t["key"]: t["id"] for t in planner.tasks(room)}


def test_two_tasks_get_different_relevant_contexts(api, room):
    ids, tasks = _approved(api, room)

    ui = context.build(tasks["ui"])
    db = context.build(tasks["db"])

    assert f"spec:{ids['cart']}" in ui["markdown"] and "Users can add items" in ui["markdown"]
    assert f"spec:{ids['cart']}" not in db["markdown"]  # unrelated requirement excluded
    assert f"spec:{ids['sqlite']}" in db["markdown"] and "shop-api" not in db["markdown"]
    assert ui["markdown"] != db["markdown"]


def test_citations_and_dependency_summaries(api, room):
    _ids, tasks = _approved(api, room)
    pack = context.build(tasks["ui"])

    cites = {i["cite"] for i in pack["items"]}
    assert f"task:{tasks['api']}" in cites  # what it depends on
    assert any(c.startswith("contract:") for c in cites)


def test_budget_is_respected_by_trimming_low_priority_items(api, room):
    _ids, tasks = _approved(api, room)
    full = context.build(tasks["api"], budget=5000)
    small = context.build(tasks["api"], budget=40)

    assert small["tokens"] <= 40 and small["trimmed"]
    assert len(small["items"]) < len(full["items"])


def test_context_endpoint(api, room):
    _ids, tasks = _approved(api, room)
    r = api.get(f"/api/tasks/{tasks['ui']}/context")
    assert r.status_code == 200 and r.json()["markdown"].startswith("# Task ui")
    assert api.get(f"/api/tasks/{tasks['ui']}/context", params={"budget": 5}).status_code == 400
    assert api.get("/api/tasks/999999/context").status_code == 404
