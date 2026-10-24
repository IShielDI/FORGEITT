"""Observer agent (stage 7): turns new chat messages into *proposed* spec items.

It never confirms anything: only a human does that (stage 8). Chat text is untrusted, so it is sent
to the model as JSON data, and the model's reply is validated against a schema before use.
"""

import json
import re
from typing import Literal

from pydantic import BaseModel, Field

from app.core.db import ex, now, q, q1
from app.llm import prompts
from app.llm.client import LLMClient, get_client
from app.services import chat

WINDOW = 40  # messages sent per observation
BATCH = 3  # new messages that make an observation due
IDLE_S = 60  # ...or this long since the oldest unobserved message
MAX_ITEMS = 20


class ObservedItem(BaseModel):
    kind: Literal["requirement", "decision", "suggestion", "question"]
    text: str = Field(min_length=1, max_length=500)
    source_message_ids: list[int] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)


class ObserverReply(BaseModel):
    items: list[ObservedItem] = Field(default_factory=list, max_length=MAX_ITEMS)


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]+", "", re.sub(r"\s+", " ", text.lower())).strip()


def _cursor(room_id: int) -> int:
    row = q1("SELECT observer_cursor FROM rooms WHERE id=?", (room_id,))
    return int(row["observer_cursor"] or 0) if row else 0


def due(room_id: int) -> bool:
    new = chat.since(room_id, _cursor(room_id), limit=BATCH)
    return len(new) >= BATCH or bool(new and now() - new[0]["ts"] >= IDLE_S)


def observe(room_id: int, client: LLMClient | None = None) -> list[int]:
    """Read messages since the cursor and store new proposed items. Returns the new item ids.
    The cursor only moves after a successful call, so a failed call is retried later."""
    window = chat.since(room_id, _cursor(room_id), limit=WINDOW)
    if not window:
        return []
    existing = q(
        "SELECT kind, text, status FROM spec_items WHERE room_id=? AND status!='superseded'",
        (room_id,),
    )
    prompt = prompts.load("observer")
    payload = {
        "current_spec": [
            {"kind": e["kind"], "text": e["text"]} for e in existing if e["status"] != "rejected"
        ],
        "messages": [{"id": m["id"], "author": m["author"], "text": m["body"]} for m in window],
    }
    client = client or get_client(room_id, label="observer")
    reply = client.complete(
        [{"role": "user", "content": json.dumps(payload)}],
        schema=ObserverReply,
        system=prompt.text,
        prompt_version=prompt.tag,
    )
    if not isinstance(reply.data, ObserverReply):
        raise ValueError("observer reply did not match the schema")
    window_ids = {m["id"] for m in window}
    seen = {normalize(e["text"]) for e in existing}
    created: list[int] = []
    for item in reply.data.items:
        sources = sorted({i for i in item.source_message_ids if i in window_ids})
        key = normalize(item.text)
        if not sources or not key or key in seen:
            continue  # uncited (possibly invented) or duplicate
        seen.add(key)
        created.append(
            ex(
                "INSERT INTO spec_items(room_id,kind,text,status,source_message_ids,confidence,created) "
                "VALUES(?,?,?,'proposed',?,?,?)",
                (
                    room_id,
                    item.kind,
                    item.text.strip(),
                    json.dumps(sources),
                    item.confidence,
                    now(),
                ),
            )
        )
    ex("UPDATE rooms SET observer_cursor=? WHERE id=?", (window[-1]["id"], room_id))
    return created
