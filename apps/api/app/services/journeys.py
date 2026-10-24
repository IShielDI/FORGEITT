"""Referee journeys drafted from approved requirements (stage 21).

The model may draft a journey; a human reviews and approves it before the referee ever uses it.
Drafts and approved journeys live in the room folder, outside every repo and agent workspace.
"""

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.llm import prompts
from app.llm.client import LLMClient, get_client
from app.services import referee, spec


class JourneyDraft(BaseModel):
    goal: str = Field(min_length=10, max_length=2000)
    success_text: str = Field(default="", max_length=200)
    db_check: str = Field(default="", max_length=500)
    source_spec_ids: list[int] = Field(default_factory=list)


def draft_path(room_id: int) -> Path:
    return referee.journey_path(room_id).with_name("journey_draft.json")


def load_draft(room_id: int) -> dict[str, Any] | None:
    p = draft_path(room_id)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def draft(room_id: int, client: LLMClient | None = None) -> dict[str, Any]:
    approved = spec.approved(room_id)
    reqs = [
        i
        for i in (approved or {}).get("snapshot", {}).get("items", [])
        if i["kind"] == "requirement"
    ]
    if not reqs:
        raise ValueError("confirm at least one requirement before drafting a journey")
    prompt = prompts.load("journey")
    client = client or get_client(room_id, label="journey")
    reply = client.complete(
        [
            {
                "role": "user",
                "content": json.dumps(
                    {"requirements": [{"id": r["id"], "text": r["text"]} for r in reqs]}
                ),
            }
        ],
        schema=JourneyDraft,
        system=prompt.text,
        prompt_version=prompt.tag,
    )
    if not isinstance(reply.data, JourneyDraft):
        raise ValueError("journey reply did not match the schema")
    d = reply.data.model_dump()
    d["source_spec_ids"] = sorted(set(d["source_spec_ids"]) & {r["id"] for r in reqs})
    d.update(status="draft", prompt=prompt.tag)
    p = draft_path(room_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d, indent=1), encoding="utf-8")
    return d


def approve(room_id: int, edits: dict[str, str] | None = None) -> dict[str, Any]:
    """A human approves the draft (optionally edited). Only then does the referee use it."""
    d = load_draft(room_id)
    if not d:
        raise ValueError("there is no journey draft to approve")
    d = {
        **d,
        **{
            k: v
            for k, v in (edits or {}).items()
            if k in ("goal", "success_text", "db_check") and v is not None
        },
    }
    saved = referee.save_journey(
        room_id, d["goal"], d.get("success_text", ""), d.get("db_check", "")
    )
    draft_path(room_id).unlink(missing_ok=True)
    return saved
