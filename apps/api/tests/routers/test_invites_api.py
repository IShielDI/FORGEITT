"""Stage 3 API: create workspaces, invite, accept, roles and access control (logins ON)."""

import pytest

from app.core import config
from app.services import mail


@pytest.fixture()
def team(api, monkeypatch):
    monkeypatch.setattr(config, "REQUIRE_AUTH", True)
    monkeypatch.setattr(mail, "send_invite", lambda *a: False)
    r = api.post(
        "/api/rooms",
        json={
            "name": "Invite Room",
            "template": "blank",
            "members": [{"name": "riya"}, {"name": "aman"}],
        },
    ).json()
    heads = {m["name"]: {"Authorization": f"Bearer {m['token']}"} for m in r["members"]}
    return r["id"], heads


def _join(api, rid, owner_headers, role="member", name="zed"):
    inv = api.post(f"/api/rooms/{rid}/invites", json={"role": role}, headers=owner_headers).json()
    joined = api.post(f"/api/invites/{inv['token']}/accept", json={"name": name}).json()
    return inv, {"Authorization": f"Bearer {joined['token']}"}


def test_slug_is_a_label_not_a_credential(api, team):
    rid, h = team
    room = api.get(f"/api/rooms/{rid}", headers=h["riya"]).json()["room"]

    assert room["slug"] == "invite-room"
    assert (
        api.get(f"/api/rooms/{rid}", headers={"Authorization": "Bearer invite-room"}).status_code
        == 401
    )


def test_only_the_owner_can_invite(api, team):
    rid, h = team

    assert api.post(f"/api/rooms/{rid}/invites", json={}, headers=h["aman"]).status_code == 403
    assert api.post(f"/api/rooms/{rid}/invites", json={}).status_code == 401
    assert api.post(f"/api/rooms/{rid}/invites", json={}, headers=h["riya"]).status_code == 200


def test_accept_valid_used_and_unknown(api, team):
    rid, h = team
    inv, zed = _join(api, rid, h["riya"])

    assert api.get(f"/api/rooms/{rid}", headers=zed).status_code == 200
    again = api.post(f"/api/invites/{inv['token']}/accept", json={"name": "yan"})
    assert again.status_code == 410
    assert api.post("/api/invites/nope/accept", json={"name": "yan"}).status_code == 404
    assert api.get(f"/api/invites/{inv['token']}").status_code == 410


def test_expired_invite_returns_410(api, team):
    from app.core.db import ex

    rid, h = team
    inv = api.post(f"/api/rooms/{rid}/invites", json={}, headers=h["riya"]).json()
    ex("UPDATE invites SET expires=1 WHERE id=?", (inv["id"],))

    assert api.post(f"/api/invites/{inv['token']}/accept", json={"name": "yan"}).status_code == 410


def test_peek_shows_room_and_role(api, team):
    rid, h = team
    inv = api.post(f"/api/rooms/{rid}/invites", json={"role": "viewer"}, headers=h["riya"]).json()

    assert api.get(f"/api/invites/{inv['token']}").json() == {
        "room_id": rid,
        "room_name": "Invite Room",
        "role": "viewer",
    }


def test_viewer_can_read_but_not_change(api, team):
    rid, h = team
    _inv, viewer = _join(api, rid, h["riya"], role="viewer", name="vee")

    assert api.get(f"/api/rooms/{rid}/me", headers=viewer).json()["role"] == "viewer"
    assert api.get(f"/api/rooms/{rid}/changes", headers=viewer).status_code == 200
    assert (
        api.post(f"/api/rooms/{rid}/contribute", json={"amount": 1}, headers=viewer).status_code
        == 403
    )
    run = api.post(f"/api/rooms/{rid}/run", json={"agent": "builder", "task": "x"}, headers=viewer)
    assert run.status_code == 403


def test_member_listing_and_non_members_rejected(api, team):
    rid, h = team
    other = api.post("/api/rooms", json={"name": "Other", "members": [{"name": "x"}]}).json()
    outsider = {"Authorization": f"Bearer {other['members'][0]['token']}"}

    roles = {
        m["name"]: m["role"] for m in api.get(f"/api/rooms/{rid}/members", headers=h["aman"]).json()
    }
    assert roles == {"riya": "owner", "aman": "member"}
    assert api.get(f"/api/rooms/{rid}/members", headers=outsider).status_code == 401
    assert api.get(f"/api/rooms/{rid}", headers=outsider).status_code == 401


def test_invite_listing_is_owner_only_and_hides_tokens(api, team):
    rid, h = team
    inv = api.post(f"/api/rooms/{rid}/invites", json={}, headers=h["riya"]).json()

    assert api.get(f"/api/rooms/{rid}/invites", headers=h["aman"]).status_code == 403
    listing = api.get(f"/api/rooms/{rid}/invites", headers=h["riya"])
    assert listing.status_code == 200 and inv["token"] not in listing.text
