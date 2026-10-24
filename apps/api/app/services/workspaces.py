"""Deleting a workspace: every room-scoped row, its members' keys, and its folder on disk.

Permanent. Refused while an agent is still running, so no run writes into a half-deleted room.
"""

from sqlalchemy import Table

from app.core.db import ex, q, q1
from app.models.tables import metadata
from app.services import gitops
from app.services.mirror import force_rmtree


class WorkspaceBusyError(Exception):
    pass


def _room_tables() -> list[Table]:
    """Every table with a room_id column, children before members and rooms."""
    tables = [t for t in metadata.sorted_tables if "room_id" in t.columns and t.name != "members"]
    return list(reversed(tables))


def delete(room_id: int) -> dict:
    """Remove the workspace for good. Returns what was removed (counts only)."""
    if not q1("SELECT 1 x FROM rooms WHERE id=?", (room_id,)):
        raise KeyError(room_id)
    if q1("SELECT 1 x FROM agents WHERE room_id=? AND status='running'", (room_id,)):
        raise WorkspaceBusyError("an agent is still running here: stop it first")
    members = [r["id"] for r in q("SELECT id FROM members WHERE room_id=?", (room_id,))]
    removed = {}
    for t in _room_tables():
        n = q1(f"SELECT COUNT(*) n FROM {t.name} WHERE room_id=?", (room_id,))["n"]  # noqa: S608
        if n:
            ex(f"DELETE FROM {t.name} WHERE room_id=?", (room_id,))  # noqa: S608
            removed[t.name] = n
    for mid in members:  # encrypted keys belong to the member rows being removed
        ex("DELETE FROM keys WHERE member_id=?", (mid,))
    ex("DELETE FROM members WHERE room_id=?", (room_id,))
    ex("DELETE FROM rooms WHERE id=?", (room_id,))
    removed["members"] = len(members)
    folder = gitops.room_dir(room_id)
    if folder.exists():
        force_rmtree(folder)
    return removed
