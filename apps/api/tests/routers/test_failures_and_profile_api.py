import json

from app.services import agent_runner, orchestrator
from tests.support import scenarios


def test_profile_endpoint(api, room):
    assert api.put(f"/api/rooms/{room}/profile", json={"profile": "turbo"}).status_code == 400
    assert api.put(f"/api/rooms/{room}/profile", json={"profile": "strict"}).json() == {
        "profile": "strict"
    }


def test_failures_can_be_listed_reassigned_and_resolved(api, room):
    r = agent_runner.run_task(
        room, "aman-agent", "Simplify the checkout total", provider=scenarios.bug(), summary="x"
    )
    orchestrator.submit_change(room, r["change_id"])

    open_failures = api.get(f"/api/rooms/{room}/failures").json()
    assert open_failures and open_failures[0]["content"]["confidence"] > 0
    fid = open_failures[0]["id"]

    moved = api.post(f"/api/failures/{fid}/reassign", json={"part": "database"}).json()
    assert moved["content"]["part"] == "database" and moved["content"]["assigned_to"]
    assert api.post(f"/api/failures/{fid}/reassign", json={"part": "nope"}).status_code == 400

    done = api.post(f"/api/failures/{fid}/resolve").json()
    assert done["content"]["state"] == "resolved"
    assert all(f["id"] != fid for f in api.get(f"/api/rooms/{room}/failures").json())
    assert json.dumps(done)  # serialisable evidence
