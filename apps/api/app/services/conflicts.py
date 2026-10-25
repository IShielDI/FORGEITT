"""Spec conflicts: two items that contradict each other, such as "add an add-to-cart button" and
later "remove the add-to-cart button".

People settle it, never the AI. Everyone can pick an option. When every member who argued (the
authors of the chat messages behind either item) has picked the same option, it is applied. If
they disagree, the owner makes the final call. The winner is confirmed; the loser is rejected, or
superseded if it was already confirmed (confirmed items are never deleted).
"""

import json
from typing import Any

from app.core.db import ex, now, q, q1
from app.services import spec

BOTH = 0  # the owner's "both can stand" choice


class ConflictError(ValueError):
    pass


def open_conflict(room_id: int, earlier: int, later: int) -> int | None:
    """Record that `later` reverses `earlier`. Skips pairs that are already open."""
    if earlier == later:
        return None
    if q1(
        "SELECT 1 x FROM spec_conflicts WHERE room_id=? AND status='open' AND "
        "((item_a=? AND item_b=?) OR (item_a=? AND item_b=?))",
        (room_id, earlier, later, later, earlier),
    ):
        return None
    cid = ex(
        "INSERT INTO spec_conflicts(room_id,item_a,item_b,status,created) VALUES(?,?,?,'open',?)",
        (room_id, earlier, later, now()),
    )
    settle_if_agreed(cid)  # e.g. one person said both sides: their latest word stands
    return cid


def stances(c: dict[str, Any]) -> dict[int, int]:
    """Which side each person involved is on. An explicit pick (button or chat reply) wins;
    otherwise people back what they said themselves (their latest side if they said both)."""
    picks = {
        r["member_id"]: r["choice"]
        for r in q("SELECT member_id, choice FROM conflict_votes WHERE conflict_id=?", (c["id"],))
    }
    earlier_by, latest_by = _authors(c["item_a"]), _authors(c["item_b"])
    out = {}
    for person in involved(c):
        if person in picks:
            out[person] = picks[person]
        elif person in latest_by:
            out[person] = c["item_b"]
        elif person in earlier_by:
            out[person] = c["item_a"]
    return out


def settle_if_agreed(conflict_id: int, by: int | None = None) -> bool:
    """Apply the side everyone involved is on, if they all agree."""
    c = _get(conflict_id)
    if c["status"] != "open":
        return False
    sides = stances(c)
    chosen = set(sides.values())
    if not sides or len(chosen) != 1 or len(sides) != len(involved(c)):
        return False
    how = "self" if len(sides) == 1 else "agreement"
    resolve(conflict_id, chosen.pop(), by or next(iter(sides)), how)
    return True


def in_open_conflict(item_id: int) -> bool:
    return bool(
        q1(
            "SELECT 1 x FROM spec_conflicts WHERE status='open' AND (item_a=? OR item_b=?)",
            (item_id, item_id),
        )
    )


def _authors(item_id: int) -> set[int]:
    """Members whose chat messages an item came from (or who wrote it by hand)."""
    it = q1("SELECT source_message_ids, created_by FROM spec_items WHERE id=?", (item_id,))
    if not it:
        return set()
    ids = json.loads(it["source_message_ids"] or "[]")
    people = {it["created_by"]} if it["created_by"] else set()
    if ids:
        marks = ",".join("?" * len(ids))
        rows = q(f"SELECT DISTINCT member_id FROM messages WHERE id IN ({marks})", ids)  # noqa: S608
        people |= {r["member_id"] for r in rows if r["member_id"]}
    return people


def involved(c: dict[str, Any]) -> set[int]:
    """Everyone who argued: the authors of either side, plus anyone who agreed with a side in chat."""
    chat = q(
        "SELECT member_id FROM conflict_votes WHERE conflict_id=? AND source_message_id IS NOT NULL",
        (c["id"],),
    )
    return _authors(c["item_a"]) | _authors(c["item_b"]) | {r["member_id"] for r in chat}


def _get(conflict_id: int) -> dict[str, Any]:
    c = q1("SELECT * FROM spec_conflicts WHERE id=?", (conflict_id,))
    if not c:
        raise LookupError("no such conflict")
    return c


def vote(
    conflict_id: int, member_id: int, choice: int, source_message_id: int | None = None
) -> dict[str, Any]:
    """Record a member's pick (a button press, or a chat reply when source_message_id is set).
    Applies it when everyone who argued picked the same option."""
    c = _get(conflict_id)
    if c["status"] != "open":
        raise ConflictError("this conflict is already settled")
    if choice not in (c["item_a"], c["item_b"]):
        raise ConflictError("pick one of the two options in this conflict")
    ex(
        "INSERT INTO conflict_votes(room_id,conflict_id,member_id,choice,source_message_id,created) "
        "VALUES(?,?,?,?,?,?) ON CONFLICT(conflict_id,member_id) DO UPDATE SET "
        "choice=excluded.choice, created=excluded.created, "
        "source_message_id=COALESCE(excluded.source_message_id, conflict_votes.source_message_id)",
        (c["room_id"], conflict_id, member_id, choice, source_message_id, now()),
    )
    settle_if_agreed(conflict_id, member_id)
    return view(_get(conflict_id))


def decide(conflict_id: int, owner_id: int | None, choice: int) -> dict[str, Any]:
    """The owner's final call (the router checks that the caller is the owner).
    choice 0 means "both can stand": it was not a real conflict, so both items stay as they are."""
    c = _get(conflict_id)
    if c["status"] != "open":
        raise ConflictError("this conflict is already settled")
    if choice == BOTH:
        ex(
            "UPDATE spec_conflicts SET status='resolved', decided_how='both', decided_by=?, "
            "decided=? WHERE id=?",
            (owner_id, now(), conflict_id),
        )
        return view(_get(conflict_id))
    if choice not in (c["item_a"], c["item_b"]):
        raise ConflictError("pick one of the two options in this conflict")
    return resolve(conflict_id, choice, owner_id, "owner")


def resolve(conflict_id: int, winner: int, by: int | None, how: str) -> dict[str, Any]:
    c = _get(conflict_id)
    loser = c["item_b"] if winner == c["item_a"] else c["item_a"]
    ex(
        "UPDATE spec_conflicts SET status='resolved', winner_id=?, decided_how=?, decided_by=?, "
        "decided=? WHERE id=?",
        (winner, how, by, now(), conflict_id),
    )
    w = spec.get(winner)
    if w["status"] == "proposed":
        spec.confirm(winner, by)
    lose = spec.get(loser)
    if lose["status"] == "proposed":
        spec.reject(loser, by)
    elif lose["status"] == "confirmed":
        ex("UPDATE spec_items SET status='superseded', decided=? WHERE id=?", (now(), loser))
        spec.snapshot(c["room_id"], by)
    return view(_get(conflict_id))


def plan_stale(room_id: int) -> list[str]:
    """Keys of planned tasks still built on a spec item that a settled conflict replaced."""
    gone = {
        r["id"]
        for r in q(
            "SELECT id FROM spec_items WHERE room_id=? AND status IN ('superseded','rejected')",
            (room_id,),
        )
    }
    stale = []
    for t in q(
        "SELECT key, spec_item_ids FROM tasks WHERE room_id=? AND status IN ('proposed','approved')",
        (room_id,),
    ):
        if gone & set(json.loads(t["spec_item_ids"] or "[]")):
            stale.append(t["key"])
    return stale


def view(c: dict[str, Any]) -> dict[str, Any]:
    names = {
        r["id"]: r["name"]
        for r in q("SELECT id, name FROM members WHERE room_id=?", (c["room_id"],))
    }
    votes = q("SELECT member_id, choice FROM conflict_votes WHERE conflict_id=?", (c["id"],))
    backing = stances(c) if c["status"] == "open" else {}

    def side(item_id: int) -> dict[str, Any]:
        it = spec.get(item_id)
        return {
            "id": item_id,
            "kind": it["kind"],
            "text": it["text"],
            "status": it["status"],
            "by": sorted(names.get(m, "?") for m in _authors(item_id)),
            "picked_by": sorted(
                names.get(v["member_id"], "?") for v in votes if v["choice"] == item_id
            ),
            "backed_by": sorted(
                names.get(p, "?") for p, side in backing.items() if side == item_id
            ),
        }

    return {
        "id": c["id"],
        "status": c["status"],
        "earlier": side(c["item_a"]),
        "latest": side(c["item_b"]),
        "involved": sorted(names.get(m, "?") for m in involved(c)),
        "winner_id": c["winner_id"],
        "decided_how": c["decided_how"],
    }


def listing(room_id: int) -> list[dict[str, Any]]:
    return [
        view(c)
        for c in q("SELECT * FROM spec_conflicts WHERE room_id=? ORDER BY id DESC", (room_id,))
    ]
