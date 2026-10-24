"""Live progress: what an agent is doing, stored as small rows the UI streams. Never contains keys or hidden tests."""

import json

from app.core.db import ex, now, q


def emit(room, agent, kind, data=None):
    return ex(
        "INSERT INTO events(room_id,agent,kind,data,ts) VALUES(?,?,?,?,?)",
        (room, agent, kind, json.dumps(data or {}, default=str)[:4000], now()),
    )


def since(room, after=0, limit=200):
    rows = q(
        "SELECT * FROM events WHERE room_id=? AND id>? ORDER BY id LIMIT ?", (room, after, limit)
    )
    for r in rows:
        r["data"] = json.loads(r["data"] or "{}")
    return rows
