"""Chat API: message history, posting, and a WebSocket that streams new messages to room members."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from app.core import auth
from app.core.db import q1
from app.services import chat

router = APIRouter()

WS_POLICY_VIOLATION = 1008


class MessageIn(BaseModel):
    body: str
    member_id: int | None = None


def _room(rid: int) -> None:
    if not q1("SELECT 1 x FROM rooms WHERE id=?", (rid,)):
        raise HTTPException(404, "room not found")


@router.get("/api/rooms/{rid}/messages")
def list_messages(
    rid: int, request: Request, before: int | None = None, limit: int = 50
) -> list[dict[str, Any]]:
    _room(rid)
    auth.actor(request, rid)
    return chat.history(rid, before, limit)


@router.post("/api/rooms/{rid}/messages")
async def post_message(rid: int, body: MessageIn, request: Request) -> dict[str, Any]:
    _room(rid)
    m = auth.writer(request, rid, body.member_id)
    if not m:
        raise HTTPException(400, "say who you are (member_id)")
    try:
        msg = chat.post(rid, m["id"], body.body)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    await chat.manager.broadcast(rid, {"type": "message", "message": msg})
    return msg


@router.websocket("/api/rooms/{rid}/ws")
async def chat_socket(
    ws: WebSocket, rid: int, token: str | None = None, member: int | None = None
) -> None:
    """Authenticate with ?token=<member token>.

    Send {"body": "..."} to post; receive {"type": "message", "message": {...}}.
    """
    m = auth.member_from_token(rid, token, member)
    if not m:
        await ws.close(code=WS_POLICY_VIOLATION)
        return
    await ws.accept()
    chat.manager.connect(rid, ws)
    try:
        while True:
            data = await ws.receive_json()
            if auth.role_of(m) == "viewer":
                await ws.send_json({"type": "error", "detail": "viewers are read-only"})
                continue
            try:
                msg = chat.post(rid, m["id"], str((data or {}).get("body", "")))
            except ValueError as e:
                await ws.send_json({"type": "error", "detail": str(e)})
                continue
            await chat.manager.broadcast(rid, {"type": "message", "message": msg})
    except WebSocketDisconnect:
        pass
    finally:
        chat.manager.disconnect(rid, ws)
