import json

from app.core.db import ex, now
from app.llm import client as llm
from app.llm.providers import MockChat
from app.services import chat
from tests.integration.test_platform import ids


def test_spec_flow_through_the_api(api, room):
    m = ids(api, room)
    mid = chat.post(room, m["riya"], "Could we add dark mode?")["id"]
    reply = {
        "items": [
            {
                "kind": "suggestion",
                "text": "Dark mode",
                "source_message_ids": [mid],
                "confidence": 0.5,
            }
        ]
    }
    llm.use_provider(MockChat([json.dumps(reply)]))
    try:
        assert api.post(f"/api/rooms/{room}/observe").json()["created"]
    finally:
        llm.use_provider(None)

    item = api.get(f"/api/rooms/{room}/spec").json()["items"][0]
    assert item["status"] == "proposed" and item["source_message_ids"] == [mid]
    done = api.post(f"/api/spec/items/{item['id']}/confirm").json()
    assert done["kind"] == "decision"
    assert api.post(f"/api/spec/items/{item['id']}/confirm").status_code == 400
    assert api.get(f"/api/rooms/{room}/spec").json()["approved"]["version"] == 1
    edited = api.post(
        f"/api/spec/items/{item['id']}/edit", json={"text": "Dark mode toggle"}
    ).json()
    assert edited["supersedes_id"] == item["id"]


def test_unknown_item_and_failed_observer(api, room):
    assert api.post("/api/spec/items/999999/confirm").status_code == 404
    ex("INSERT INTO messages(room_id,member_id,body,ts) VALUES(?,?,?,?)", (room, 1, "hi", now()))
    llm.use_provider(MockChat(["no json", "still no json"]))
    try:
        assert api.post(f"/api/rooms/{room}/observe").status_code == 503
    finally:
        llm.use_provider(None)
