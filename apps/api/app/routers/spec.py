"""Spec API (stages 7-8): the living spec, observer runs, and human confirm/reject/edit."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core import auth
from app.core.db import q1
from app.llm.client import LLMError
from app.services import credits, observer, spec

router = APIRouter()


class EditIn(BaseModel):
    text: str
    kind: str | None = None


def _room(rid: int) -> None:
    if not q1("SELECT 1 x FROM rooms WHERE id=?", (rid,)):
        raise HTTPException(404, "room not found")


def _actor_id(m: dict[str, Any] | None) -> int | None:
    return m["id"] if m else None


@router.get("/api/rooms/{rid}/spec")
def get_spec(rid: int, request: Request) -> dict[str, Any]:
    _room(rid)
    auth.actor(request, rid)
    return {"items": spec.items(rid), "approved": spec.approved(rid)}


@router.post("/api/rooms/{rid}/observe")
def observe_now(rid: int, request: Request) -> dict[str, Any]:
    """Run the observer on new messages now (it also runs in the background)."""
    _room(rid)
    auth.writer(request, rid)
    try:
        created = observer.observe(rid)
    except (LLMError, credits.BudgetExceededError) as e:
        raise HTTPException(503, f"observer could not run: {e}") from e
    return {"created": created}


def _act(item_id: int, request: Request, action: str, body: EditIn | None = None) -> dict[str, Any]:
    try:
        item = spec.get(item_id)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e
    m = auth.writer(request, item["room_id"])
    try:
        if action == "confirm":
            return spec.confirm(item_id, _actor_id(m))
        if action == "reject":
            return spec.reject(item_id, _actor_id(m))
        if body is None:
            raise HTTPException(400, "edit needs a body")
        return spec.edit(item_id, _actor_id(m), body.text, body.kind)
    except spec.SpecError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/api/spec/items/{item_id}/confirm")
def confirm(item_id: int, request: Request) -> dict[str, Any]:
    return _act(item_id, request, "confirm")


@router.post("/api/spec/items/{item_id}/reject")
def reject(item_id: int, request: Request) -> dict[str, Any]:
    return _act(item_id, request, "reject")


@router.post("/api/spec/items/{item_id}/edit")
def edit(item_id: int, body: EditIn, request: Request) -> dict[str, Any]:
    return _act(item_id, request, "edit", body)
