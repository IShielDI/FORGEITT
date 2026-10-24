"""Stage 4: realtime chat over WebSocket plus REST history (logins ON)."""

import pytest
from starlette.websockets import WebSocketDisconnect

from app.core import config
from app.services import mail


@pytest.fixture()
def team(api, monkeypatch):
    monkeypatch.setattr(config, "REQUIRE_AUTH", True)
    monkeypatch.setattr(mail, "send_invite", lambda *a: False)
    r = api.post(
        "/api/rooms",
        json={"name": "Chat", "template": "blank", "members": [{"name": "riya"}, {"name": "aman"}]},
    ).json()
    return r["id"], {m["name"]: m["token"] for m in r["members"]}


def test_two_clients_receive_each_others_messages_in_order(api, team):
    rid, tok = team
    with (
        api.websocket_connect(f"/api/rooms/{rid}/ws?token={tok['riya']}") as a,
        api.websocket_connect(f"/api/rooms/{rid}/ws?token={tok['aman']}") as b,
    ):
        a.send_json({"body": "hello from riya"})
        b.send_json({"body": "hi riya"})
        got_a = [a.receive_json()["message"]["body"] for _ in range(2)]
        got_b = [b.receive_json()["message"]["body"] for _ in range(2)]

    assert got_a == got_b == ["hello from riya", "hi riya"]
    history = api.get(
        f"/api/rooms/{rid}/messages", headers={"Authorization": f"Bearer {tok['aman']}"}
    ).json()
    assert [(m["author"], m["body"]) for m in history] == [
        ("riya", "hello from riya"),
        ("aman", "hi riya"),
    ]


def test_rest_post_fans_out_to_sockets(api, team):
    rid, tok = team
    with api.websocket_connect(f"/api/rooms/{rid}/ws?token={tok['aman']}") as b:
        r = api.post(
            f"/api/rooms/{rid}/messages",
            json={"body": "via REST"},
            headers={"Authorization": f"Bearer {tok['riya']}"},
        )
        assert r.status_code == 200
        assert b.receive_json()["message"]["body"] == "via REST"


def test_non_members_are_rejected(api, team):
    rid, _tok = team
    other = api.post("/api/rooms", json={"name": "Other", "members": [{"name": "x"}]}).json()
    outsider = other["members"][0]["token"]

    for url in (f"/api/rooms/{rid}/ws?token={outsider}", f"/api/rooms/{rid}/ws"):
        with pytest.raises(WebSocketDisconnect), api.websocket_connect(url) as ws:
            ws.receive_json()
    assert (
        api.get(
            f"/api/rooms/{rid}/messages", headers={"Authorization": f"Bearer {outsider}"}
        ).status_code
        == 401
    )


def test_viewer_can_read_but_not_post(api, team):
    rid, tok = team
    owner = {"Authorization": f"Bearer {tok['riya']}"}
    inv = api.post(f"/api/rooms/{rid}/invites", json={"role": "viewer"}, headers=owner).json()
    vtok = api.post(f"/api/invites/{inv['token']}/accept", json={"name": "vee"}).json()["token"]

    assert (
        api.post(
            f"/api/rooms/{rid}/messages",
            json={"body": "x"},
            headers={"Authorization": f"Bearer {vtok}"},
        ).status_code
        == 403
    )
    with api.websocket_connect(f"/api/rooms/{rid}/ws?token={vtok}") as v:
        v.send_json({"body": "x"})
        assert v.receive_json()["type"] == "error"


def test_history_pagination(api, team):
    rid, tok = team
    h = {"Authorization": f"Bearer {tok['riya']}"}
    ids = [
        api.post(f"/api/rooms/{rid}/messages", json={"body": f"m{i}"}, headers=h).json()["id"]
        for i in range(4)
    ]

    page = api.get(
        f"/api/rooms/{rid}/messages", params={"before": ids[2], "limit": 1}, headers=h
    ).json()
    assert [m["body"] for m in page] == ["m1"]
