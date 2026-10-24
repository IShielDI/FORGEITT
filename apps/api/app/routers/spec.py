"""Spec API (stages 7-8): the living spec, observer runs, and human confirm/reject/edit."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core import auth, config
from app.core.db import q1
from app.llm.client import LLMError
from app.services import conflicts, credits, observer, spec

router = APIRouter()


class PickIn(BaseModel):
    choice: int  # the spec item id picked
    member_id: int | None = None  # only used when logins are off (tests, local scripts)


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
    return {
        "items": spec.items(rid),
        "approved": spec.approved(rid),
        "conflicts": conflicts.listing(rid),
        "plan_stale": conflicts.plan_stale(rid),
    }


def _conflict_room(conflict_id: int) -> int:
    row = q1("SELECT room_id FROM spec_conflicts WHERE id=?", (conflict_id,))
    if not row:
        raise HTTPException(404, "no such conflict")
    return int(row["room_id"])


@router.post("/api/spec/conflicts/{conflict_id}/vote")
def vote_conflict(conflict_id: int, body: PickIn, request: Request) -> dict[str, Any]:
    """Pick one side. If everyone who argued picks the same side, it is applied."""
    rid = _conflict_room(conflict_id)
    m = auth.writer(request, rid, body.member_id)
    if not m:
        raise HTTPException(400, "say who you are (member_id)")
    try:
        return conflicts.vote(conflict_id, m["id"], body.choice)
    except conflicts.ConflictError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/api/spec/conflicts/{conflict_id}/decide")
def decide_conflict(conflict_id: int, body: PickIn, request: Request) -> dict[str, Any]:
    """The owner's final call, for when the people who argued do not agree."""
    rid = _conflict_room(conflict_id)
    m = (
        auth.owner(request, rid)
        if config.REQUIRE_AUTH
        else auth.writer(request, rid, body.member_id)
    )
    try:
        return conflicts.decide(conflict_id, m["id"] if m else None, body.choice)
    except conflicts.ConflictError as e:
        raise HTTPException(400, str(e)) from e


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
