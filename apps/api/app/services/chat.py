"""Team chat: persisted messages, paginated history and realtime fan-out to connected members.

Chat text is untrusted input. It is stored as plain text, never rendered as HTML, and size-limited.
"""

import asyncio
from collections import defaultdict
from typing import Any, Protocol

from app.core.db import ex, now, q, q1

MAX_BODY = 4000
DEFAULT_PAGE = 50
MAX_PAGE = 200


class Socket(Protocol):
    async def send_json(self, data: Any) -> None: ...


def post(room_id: int, member_id: int, body: str) -> dict[str, Any]:
    text = (body or "").strip()
    if not text:
        raise ValueError("message is empty")
    if len(text) > MAX_BODY:
        raise ValueError(f"message is longer than {MAX_BODY} characters")
    mid = ex(
        "INSERT INTO messages(room_id,member_id,body,ts) VALUES(?,?,?,?)",
        (room_id, member_id, text, now()),
    )
    return get(mid)


def get(message_id: int) -> dict[str, Any]:
    row = q1(
        "SELECT m.id, m.room_id, m.member_id, mb.name AS author, m.body, m.ts "
        "FROM messages m LEFT JOIN members mb ON mb.id = m.member_id WHERE m.id=?",
        (message_id,),
    )
    if row is None:
        raise ValueError("no such message")
    return row


def history(
    room_id: int, before: int | None = None, limit: int = DEFAULT_PAGE
) -> list[dict[str, Any]]:
    """Oldest-first page of messages, optionally older than message id `before`."""
    limit = max(1, min(limit, MAX_PAGE))
    sql = (
        "SELECT m.id, m.room_id, m.member_id, mb.name AS author, m.body, m.ts "
        "FROM messages m LEFT JOIN members mb ON mb.id = m.member_id WHERE m.room_id=?"
    )
    args: list[Any] = [room_id]
    if before is not None:
        sql += " AND m.id < ?"
        args.append(before)
    rows = q(sql + " ORDER BY m.id DESC LIMIT ?", [*args, limit])
    return list(reversed(rows))


def since(room_id: int, after: int, limit: int = MAX_PAGE) -> list[dict[str, Any]]:
    """Messages newer than id `after` (used by the observer and by polling clients)."""
    return q(
        "SELECT m.id, m.room_id, m.member_id, mb.name AS author, m.body, m.ts "
        "FROM messages m LEFT JOIN members mb ON mb.id = m.member_id "
        "WHERE m.room_id=? AND m.id > ? ORDER BY m.id LIMIT ?",
        (room_id, after, limit),
    )


class ConnectionManager:
    """Open WebSockets per room. Broadcasts preserve the order messages were stored in.

    Each socket is sent to on the event loop that owns it (one loop under uvicorn; tests may use several).
    """

    def __init__(self) -> None:
        self.rooms: dict[int, dict[Socket, asyncio.AbstractEventLoop]] = defaultdict(dict)

    def connect(self, room_id: int, ws: Socket) -> None:
        self.rooms[room_id][ws] = asyncio.get_running_loop()

    def disconnect(self, room_id: int, ws: Socket) -> None:
        self.rooms[room_id].pop(ws, None)

    async def broadcast(self, room_id: int, payload: dict[str, Any]) -> None:
        here = asyncio.get_running_loop()
        for ws, loop in list(self.rooms[room_id].items()):
            try:
                if loop is here:
                    await ws.send_json(payload)
                else:
                    fut = asyncio.run_coroutine_threadsafe(ws.send_json(payload), loop)
                    await asyncio.wrap_future(fut)
            except Exception:  # a closed socket must not stop the others
                self.disconnect(room_id, ws)


manager = ConnectionManager()
