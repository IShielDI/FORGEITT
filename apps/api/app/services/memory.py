"""Shared project memory. Every entry has an owner and an expiry; agents write only about their own part;
the referee's journeys and hidden tests are never stored here."""

import json

from app.core.db import ex, now, q, q1

KINDS = {"decision", "contract", "graph", "handoff", "checkpoint", "failure", "contract-change"}
PLATFORM_ONLY = {"graph", "checkpoint", "failure"}
DEFAULT_TTL = {"handoff": 3 * 86400}


def add(room, kind, author, content, part=None, ttl=None, by_platform=False):
    if kind not in KINDS:
        raise ValueError("unknown kind")
    if kind in PLATFORM_ONLY and not by_platform:
        raise PermissionError(f"only the platform writes {kind} entries")
    if kind == "contract" and not by_platform:
        raise PermissionError("contracts change only through a contract-change request")
    if kind == "handoff" and not by_platform:
        a = q1("SELECT part FROM agents WHERE room_id=? AND name=?", (room, author))
        if not a or a["part"] != part:
            raise PermissionError("an agent writes only about its own part")
    ttl = ttl if ttl is not None else DEFAULT_TTL.get(kind)
    return ex(
        "INSERT INTO memory(room_id,kind,part,author,content,ts,expires) VALUES(?,?,?,?,?,?,?)",
        (
            room,
            kind,
            part,
            author,
            content if isinstance(content, str) else json.dumps(content),
            now(),
            now() + ttl if ttl else None,
        ),
    )


def sweep(room: int) -> None:
    """Flag expired entries for review rather than deleting them."""
    ex(
        "UPDATE memory SET flagged=1 WHERE room_id=? AND expires IS NOT NULL AND expires<?",
        (room, now()),
    )


def listing(room, kind=None, part=None):
    sweep(room)
    sql, args = "SELECT * FROM memory WHERE room_id=?", [room]
    if kind:
        sql += " AND kind=?"
        args.append(kind)
    if part:
        sql += " AND part=?"
        args.append(part)
    return q(sql + " ORDER BY id", args)


def excerpts(room, part, limit=8):
    """Only the relevant memory for one agent's task: whole-project decisions and contracts, plus its own part's notes
    and what it depends on. Stale (flagged) entries are marked so the agent treats them as input to check, not truth."""
    rows = [
        m
        for m in listing(room)
        if m["kind"] in ("decision", "contract") or m["part"] == part or m["kind"] == "handoff"
    ]
    rows = rows[-limit:]
    return [
        f"[{m['kind']}{' STALE' if m['flagged'] else ''} by {m['author']} for {m['part'] or 'project'}] {m['content']}"
        for m in rows
    ]


def contract_change_request(room, agent, part, proposal):
    return add(
        room,
        "contract-change",
        agent,
        {"part": part, "proposal": proposal, "status": "pending"},
        part=part,
        by_platform=True,
    )


def approve_contract_change(room, request_id, approver):
    m = q1(
        "SELECT * FROM memory WHERE id=? AND room_id=? AND kind='contract-change'",
        (request_id, room),
    )
    body = json.loads(m["content"])
    body["status"] = "approved"
    body["approved_by"] = approver
    ex("UPDATE memory SET content=? WHERE id=?", (json.dumps(body), request_id))
    return add(room, "contract", approver, body["proposal"], part=body["part"], by_platform=True)
