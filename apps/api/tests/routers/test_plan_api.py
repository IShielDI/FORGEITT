from app.llm import client as llm
from app.llm.providers import MockChat
from tests.support.planning import approved_spec, plan_reply


def test_plan_generate_edit_approve_through_the_api(api, room):
    ids = approved_spec(room)
    llm.use_provider(MockChat([plan_reply(ids)]))
    try:
        r = api.post(f"/api/rooms/{room}/plan/generate")
    finally:
        llm.use_provider(None)
    assert r.status_code == 200 and r.json()["build_order"][0] == "db"

    ui = next(t for t in r.json()["tasks"] if t["key"] == "ui")
    assert api.patch(f"/api/tasks/{ui['id']}", json={"depends_on": ["ui"]}).status_code == 400
    assert (
        api.patch(f"/api/tasks/{ui['id']}", json={"title": "Cart and checkout page"}).status_code
        == 200
    )

    approved = api.post(f"/api/rooms/{room}/plan/approve").json()
    assert {t["status"] for t in approved["tasks"]} == {"approved"}
    assert api.post(f"/api/rooms/{room}/plan/approve").status_code == 400  # nothing left to approve
    assert api.get(f"/api/tasks/{ui['id']}/trace").json()["requirement"] == [ids["cart"]]

    v2 = api.post(
        f"/api/rooms/{room}/contracts",
        json={"name": "db", "kind": "schema", "content": "users(email, name)"},
    ).json()
    assert v2["version"] == 2
    assert api.post(f"/api/contracts/{v2['id']}/approve").json()["status"] == "approved"


def test_generate_without_spec_is_a_400(api, room):
    assert api.post(f"/api/rooms/{room}/plan/generate").status_code == 400
