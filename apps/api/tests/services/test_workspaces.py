"""Deleting a workspace removes its rows, its members' keys and its folder, and nothing else."""

import pytest

from app.core.db import ex, q1
from app.services import gitops, ledger, workspaces


def _make(api, name):
    return api.post(
        "/api/rooms", json={"name": name, "members": [{"name": "a"}, {"name": "b"}]}
    ).json()["id"]


def test_delete_removes_everything_for_that_room_only(api):
    gone, kept = _make(api, "gone"), _make(api, "kept")
    member = q1("SELECT id FROM members WHERE room_id=? ORDER BY id", (gone,))["id"]
    other = q1("SELECT id FROM members WHERE room_id=? ORDER BY id", (kept,))["id"]
    ledger.add_key(member, "groq", "plain", "gsk_to_be_removed")
    ledger.add_key(other, "groq", "plain", "gsk_stays_put")
    folder = gitops.room_dir(gone)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "note.txt").write_text("x")

    removed = workspaces.delete(gone)

    assert removed["members"] == 2
    assert q1("SELECT 1 x FROM rooms WHERE id=?", (gone,)) is None
    assert q1("SELECT 1 x FROM members WHERE room_id=?", (gone,)) is None
    assert q1("SELECT 1 x FROM agents WHERE room_id=?", (gone,)) is None
    assert q1("SELECT 1 x FROM keys WHERE member_id=?", (member,)) is None
    assert not folder.exists()
    assert q1("SELECT 1 x FROM rooms WHERE id=?", (kept,))
    assert ledger.get_secret(other, "groq") == "gsk_stays_put"


def test_delete_refuses_while_an_agent_runs(api):
    rid = _make(api, "busy")
    ex("UPDATE agents SET status='running' WHERE room_id=?", (rid,))

    with pytest.raises(workspaces.WorkspaceBusyError):
        workspaces.delete(rid)
    assert q1("SELECT 1 x FROM rooms WHERE id=?", (rid,))


def test_unknown_room():
    with pytest.raises(KeyError):
        workspaces.delete(987654)
