"""Plan, contracts, knowledge and context API (stages 9-11)."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.core import auth, config
from app.core.db import ex, q1
from app.llm.client import LLMError
from app.services import conflicts, context, credits, knowledge, planner

router = APIRouter()


class TaskPatch(BaseModel):
    owner_member_id: int | None = None
    title: str | None = None
    description: str | None = None
    component: str | None = None
    depends_on: list[str] | None = None


class ContractIn(BaseModel):
    name: str
    kind: str
    content: str


def _room(rid: int) -> None:
    if not q1("SELECT 1 x FROM rooms WHERE id=?", (rid,)):
        raise HTTPException(404, "room not found")


def _owner(request: Request, rid: int) -> dict[str, Any] | None:
    return auth.owner(request, rid) if config.REQUIRE_AUTH else None


def _task(task_id: int) -> dict[str, Any]:
    try:
        return planner.task(task_id)
    except LookupError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/api/rooms/{rid}/plan")
def get_plan(rid: int, request: Request) -> dict[str, Any]:
    _room(rid)
    auth.actor(request, rid)
    return {
        "tasks": planner.tasks(rid),
        "contracts": planner.contracts(rid),
        "stale": conflicts.plan_stale(rid),  # task keys built on a replaced spec option
    }


@router.post("/api/rooms/{rid}/plan/generate")
def generate(rid: int, request: Request) -> dict[str, Any]:
    _room(rid)
    auth.writer(request, rid)
    try:
        return planner.generate(rid)
    except planner.PlanError as e:
        raise HTTPException(400, str(e)) from e
    except (LLMError, credits.BudgetExceededError) as e:
        raise HTTPException(503, f"planner could not run: {e}") from e


@router.post("/api/rooms/{rid}/plan/approve")
def approve(rid: int, request: Request) -> dict[str, Any]:
    """Owner only: approves the tasks and pins the contract versions."""
    _room(rid)
    _owner(request, rid)
    try:
        return planner.approve(rid)
    except planner.PlanError as e:
        raise HTTPException(400, str(e)) from e


@router.patch("/api/tasks/{task_id}")
def patch_task(task_id: int, body: TaskPatch, request: Request) -> dict[str, Any]:
    t = _task(task_id)
    auth.writer(request, t["room_id"])
    try:
        return planner.update_task(task_id, body.model_dump(exclude_unset=True))
    except planner.PlanError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/api/tasks/{task_id}/drop")
def drop_task(task_id: int, request: Request) -> dict[str, Any]:
    """Owner only: remove a task that has not started from the plan."""
    t = _task(task_id)
    _owner(request, t["room_id"])
    try:
        return planner.drop(task_id)
    except planner.PlanError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/api/rooms/{rid}/contracts")
def list_contracts(rid: int, request: Request) -> list[dict[str, Any]]:
    _room(rid)
    auth.actor(request, rid)
    return planner.contracts(rid)


@router.post("/api/rooms/{rid}/contracts")
def new_contract_version(rid: int, body: ContractIn, request: Request) -> dict[str, Any]:
    _room(rid)
    m = auth.writer(request, rid)
    try:
        return planner.propose_contract_version(
            rid, body.name, body.kind, body.content, m["id"] if m else None
        )
    except planner.PlanError as e:
        raise HTTPException(400, str(e)) from e


@router.post("/api/contracts/{contract_id}/approve")
def approve_contract(contract_id: int, request: Request) -> dict[str, Any]:
    c = q1("SELECT room_id FROM contracts WHERE id=?", (contract_id,))
    if not c:
        raise HTTPException(404, "no such contract")
    _owner(request, c["room_id"])
    try:
        return planner.approve_contract(contract_id)
    except planner.PlanError as e:
        raise HTTPException(400, str(e)) from e


@router.get("/api/tasks/{task_id}/trace")
def trace(task_id: int, request: Request) -> dict[str, Any]:
    t = _task(task_id)
    auth.actor(request, t["room_id"])
    return knowledge.trace_task(t["room_id"], task_id)


@router.get("/api/tasks/{task_id}/context")
def task_context(
    task_id: int, request: Request, budget: int = context.DEFAULT_BUDGET
) -> dict[str, Any]:
    t = _task(task_id)
    auth.actor(request, t["room_id"])
    if not 100 <= budget <= 20000:
        raise HTTPException(400, "budget must be between 100 and 20000 tokens")
    return context.build(task_id, budget)


# ---------- project map and edit scope ----------
class ScopeIn(BaseModel):
    scope: str


@router.get("/api/rooms/{rid}/graph")
def project_graph(rid: int, request: Request) -> dict[str, Any]:
    """The project's memory graph: spec items, contracts, tasks, parts, files, changes, failures."""
    _room(rid)
    auth.actor(request, rid)
    return knowledge.project_graph(rid)


@router.get("/api/tasks/{task_id}/files")
def task_files(task_id: int, request: Request) -> list[dict[str, str]]:
    t = _task(task_id)
    auth.actor(request, t["room_id"])
    return knowledge.relevant_files(t["room_id"], task_id)


@router.put("/api/rooms/{rid}/edit-scope")
def set_edit_scope(rid: int, body: ScopeIn, request: Request) -> dict[str, str]:
    """Owner only. `task`: a task's change may only touch its relevant files (checked at submit)."""
    _room(rid)
    _owner(request, rid)
    if body.scope not in ("off", "task"):
        raise HTTPException(400, "scope must be 'off' or 'task'")
    ex("UPDATE rooms SET edit_scope=? WHERE id=?", (body.scope, rid))
    return {"scope": body.scope}
