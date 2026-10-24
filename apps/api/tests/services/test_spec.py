import json

import pytest

from app.core.db import ex, now, q
from app.services import spec


def _item(room, kind="requirement", text="Users can log in"):
    return ex(
        "INSERT INTO spec_items(room_id,kind,text,status,created) VALUES(?,?,?,'proposed',?)",
        (room, kind, text, now()),
    )


def test_confirming_a_suggestion_makes_it_a_decision_and_snapshots(api, room):
    iid = _item(room, "suggestion", "Use SQLite")

    it = spec.confirm(iid, 1)

    assert (it["kind"], it["status"], it["confirmed_by"]) == ("decision", "confirmed", 1)
    snap = spec.approved(room)
    assert snap["version"] == 1 and [i["text"] for i in snap["snapshot"]["items"]] == ["Use SQLite"]


def test_snapshot_contains_only_confirmed_items(api, room):
    keep, drop, pending = _item(room, text="A"), _item(room, text="B"), _item(room, text="C")
    spec.reject(drop, 1)
    spec.confirm(keep, 1)

    assert [i["text"] for i in spec.approved(room)["snapshot"]["items"]] == ["A"]
    assert {i["id"]: i["status"] for i in spec.items(room)}[pending] == "proposed"


def test_confirmed_items_are_append_only(api, room):
    old = _item(room, text="Login with email")
    spec.confirm(old, 1)

    new = spec.edit(old, 2, "Login with email or Google")

    assert new["id"] != old and new["version"] == 2 and new["supersedes_id"] == old
    assert new["status"] == "proposed"
    statuses = {i["id"]: i["status"] for i in spec.items(room)}
    assert statuses[old] == "confirmed"  # still in force until the new version is confirmed
    spec.confirm(new["id"], 1)
    statuses = {i["id"]: i["status"] for i in spec.items(room)}
    assert statuses[old] == "superseded" and statuses[new["id"]] == "confirmed"
    assert spec.approved(room)["version"] == 2
    texts = [i["text"] for i in spec.approved(room)["snapshot"]["items"]]
    assert texts == ["Login with email or Google"]


def test_proposed_items_edit_in_place(api, room):
    iid = _item(room, text="Draft")
    assert spec.edit(iid, 1, "Better draft", "question")["id"] == iid


@pytest.mark.parametrize("action", ["confirm", "reject"])
def test_only_proposed_items_can_be_decided(api, room, action):
    iid = _item(room)
    spec.reject(iid, 1)
    with pytest.raises(spec.SpecError):
        getattr(spec, action)(iid, 1)


def test_one_pending_version_at_a_time(api, room):
    iid = _item(room)
    spec.confirm(iid, 1)
    spec.edit(iid, 1, "v2")
    with pytest.raises(spec.SpecError):
        spec.edit(iid, 1, "v2 again")


def test_versions_rows_are_kept(api, room):
    for t in ("A", "B"):
        spec.confirm(_item(room, text=t), 1)
    versions = q(
        "SELECT version, snapshot FROM spec_versions WHERE room_id=? ORDER BY version", (room,)
    )
    assert [v["version"] for v in versions] == [1, 2]
    assert len(json.loads(versions[1]["snapshot"])["items"]) == 2
