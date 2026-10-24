"""Living spec (stage 8): confirm, reject, edit, and versioned snapshots.

Rules (TRD R1, AGENTS invariants):
- Only a human confirms. A confirmed suggestion becomes a `decision` item.
- Confirmed items are append-only: editing one creates a new proposed version that supersedes the old
  one only when it is confirmed in turn.
- Every confirmation writes a new `spec_versions` snapshot that contains only confirmed items.
"""

import json
from typing import Any

from app.core.db import ex, now, q, q1

KINDS = ("requirement", "decision", "suggestion", "question")


class SpecError(ValueError):
    pass


def _item(item_id: int) -> dict[str, Any]:
    row = q1("SELECT * FROM spec_items WHERE id=?", (item_id,))
    if not row:
        raise LookupError("no such spec item")
    row["source_message_ids"] = json.loads(row["source_message_ids"] or "[]")
    return row


get = _item


def items(room_id: int) -> list[dict[str, Any]]:
    rows = q("SELECT * FROM spec_items WHERE room_id=? ORDER BY id", (room_id,))
    for r in rows:
        r["source_message_ids"] = json.loads(r["source_message_ids"] or "[]")
    return rows


def approved(room_id: int) -> dict[str, Any] | None:
    row = q1(
        "SELECT * FROM spec_versions WHERE room_id=? ORDER BY version DESC LIMIT 1", (room_id,)
    )
    if row:
        row["snapshot"] = json.loads(row["snapshot"])
    return row


def snapshot(room_id: int, member_id: int | None) -> int:
    confirmed = q(
        "SELECT id, kind, text, version, source_message_ids FROM spec_items "
        "WHERE room_id=? AND status='confirmed' ORDER BY id",
        (room_id,),
    )
    last = q1("SELECT MAX(version) v FROM spec_versions WHERE room_id=?", (room_id,))
    version = int((last or {}).get("v") or 0) + 1
    ex(
        "INSERT INTO spec_versions(room_id,version,snapshot,created_by,created) VALUES(?,?,?,?,?)",
        (room_id, version, json.dumps({"items": confirmed}), member_id, now()),
    )
    return version


def confirm(item_id: int, member_id: int | None) -> dict[str, Any]:
    it = _item(item_id)
    if it["status"] != "proposed":
        raise SpecError(f"only proposed items can be confirmed (this one is {it['status']})")
    kind = "decision" if it["kind"] == "suggestion" else it["kind"]
    ex(
        "UPDATE spec_items SET status='confirmed', kind=?, confirmed_by=?, decided=? WHERE id=?",
        (kind, member_id, now(), item_id),
    )
    if it["supersedes_id"]:
        ex("UPDATE spec_items SET status='superseded' WHERE id=?", (it["supersedes_id"],))
    snapshot(it["room_id"], member_id)
    return _item(item_id)


def reject(item_id: int, member_id: int | None) -> dict[str, Any]:
    it = _item(item_id)
    if it["status"] != "proposed":
        raise SpecError(f"only proposed items can be rejected (this one is {it['status']})")
    ex(
        "UPDATE spec_items SET status='rejected', confirmed_by=?, decided=? WHERE id=?",
        (member_id, now(), item_id),
    )
    return _item(item_id)


def edit(item_id: int, member_id: int | None, text: str, kind: str | None = None) -> dict[str, Any]:
    """Proposed items change in place. Confirmed items get a new proposed version (append-only)."""
    text = (text or "").strip()
    if not text or len(text) > 500:
        raise SpecError("text must be 1 to 500 characters")
    if kind is not None and kind not in KINDS:
        raise SpecError(f"kind must be one of {', '.join(KINDS)}")
    it = _item(item_id)
    if it["status"] == "proposed":
        ex("UPDATE spec_items SET text=?, kind=? WHERE id=?", (text, kind or it["kind"], item_id))
        return _item(item_id)
    if it["status"] != "confirmed":
        raise SpecError(f"{it['status']} items cannot be edited")
    if q1("SELECT 1 x FROM spec_items WHERE supersedes_id=? AND status='proposed'", (item_id,)):
        raise SpecError("there is already a pending new version of this item")
    new_id = ex(
        "INSERT INTO spec_items(room_id,kind,text,status,source_message_ids,confidence,version,"
        "supersedes_id,created_by,created) VALUES(?,?,?,'proposed',?,NULL,?,?,?,?)",
        (
            it["room_id"],
            kind or it["kind"],
            text,
            json.dumps(it["source_message_ids"]),
            it["version"] + 1,
            item_id,
            member_id,
            now(),
        ),
    )
    return _item(new_id)
