"""Planner and contracts (stage 9).

From the approved spec, the model proposes tasks (owners, dependencies, components) and shared
contracts. Everything is stored as *proposed*; the dependency graph must be acyclic; a human owner
approves the plan, which approves and pins the contract versions. A task may start only once it and
every contract it is pinned to are approved.
"""

import json
import re
from graphlib import CycleError, TopologicalSorter
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.core.db import ex, now, q, q1
from app.llm import prompts
from app.llm.client import LLMClient, get_client
from app.services import spec

KEY_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")


class PlanError(ValueError):
    pass


class PlanTask(BaseModel):
    key: str = Field(pattern=KEY_RE.pattern)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=4000)
    component: str = Field(default="", max_length=100)
    depends_on: list[str] = Field(default_factory=list)
    suggested_owner: str | None = None
    spec_item_ids: list[int] = Field(default_factory=list)
    contracts: list[str] = Field(default_factory=list)


class PlanContract(BaseModel):
    kind: Literal["api", "schema", "type"]
    name: str = Field(pattern=KEY_RE.pattern)
    content: str = Field(min_length=1, max_length=20000)
    spec_item_ids: list[int] = Field(default_factory=list)


class PlanReply(BaseModel):
    tasks: list[PlanTask] = Field(min_length=1, max_length=30)
    contracts: list[PlanContract] = Field(default_factory=list, max_length=20)


def check_acyclic(deps: dict[str, list[str]]) -> list[str]:
    """Raise PlanError on unknown dependencies or a cycle; return a valid build order."""
    for key, ds in deps.items():
        missing = [d for d in ds if d not in deps]
        if missing:
            raise PlanError(f"task {key} depends on unknown task(s): {', '.join(missing)}")
    try:
        return list(TopologicalSorter(deps).static_order())
    except CycleError as e:
        raise PlanError(f"dependency cycle: {' -> '.join(map(str, e.args[1]))}") from e


def _decode(row: dict[str, Any], *fields: str) -> dict[str, Any]:
    for f in fields:
        row[f] = json.loads(row[f] or "[]")
    return row


def tasks(room_id: int) -> list[dict[str, Any]]:
    return [
        _decode(t, "depends_on", "spec_item_ids", "contract_ids")
        for t in q("SELECT * FROM tasks WHERE room_id=? ORDER BY id", (room_id,))
    ]


def contracts(room_id: int) -> list[dict[str, Any]]:
    return [
        _decode(c, "spec_item_ids")
        for c in q("SELECT * FROM contracts WHERE room_id=? ORDER BY name, version", (room_id,))
    ]


def task(task_id: int) -> dict[str, Any]:
    row = q1("SELECT * FROM tasks WHERE id=?", (task_id,))
    if not row:
        raise LookupError("no such task")
    return _decode(row, "depends_on", "spec_item_ids", "contract_ids")


def generate(room_id: int, client: LLMClient | None = None) -> dict[str, Any]:
    approved = spec.approved(room_id)
    if not approved or not approved["snapshot"]["items"]:
        raise PlanError("confirm at least one spec item before planning")
    if q1("SELECT 1 x FROM tasks WHERE room_id=? AND status!='proposed'", (room_id,)):
        raise PlanError("a plan is already approved; change it task by task")
    items = approved["snapshot"]["items"]
    members = q("SELECT id, name FROM members WHERE room_id=? AND role!='viewer'", (room_id,))
    prompt = prompts.load("planner")
    payload = {
        "spec": [{"id": i["id"], "kind": i["kind"], "text": i["text"]} for i in items],
        "members": [m["name"] for m in members],
    }
    client = client or get_client(room_id, label="planner")
    reply = client.complete(
        [{"role": "user", "content": json.dumps(payload)}],
        schema=PlanReply,
        system=prompt.text,
        prompt_version=prompt.tag,
        max_tokens=4000,
    )
    if not isinstance(reply.data, PlanReply):
        raise PlanError("planner reply did not match the schema")
    return store_proposal(room_id, reply.data, {i["id"] for i in items}, members)


def store_proposal(
    room_id: int, plan: PlanReply, spec_ids: set[int], members: list[dict[str, Any]]
) -> dict[str, Any]:
    keys = [t.key for t in plan.tasks]
    if len(set(keys)) != len(keys):
        raise PlanError("task keys must be unique")
    names = [c.name for c in plan.contracts]
    if len(set(names)) != len(names):
        raise PlanError("contract names must be unique")
    order = check_acyclic({t.key: t.depends_on for t in plan.tasks})
    by_name = {m["name"].lower(): m["id"] for m in members}
    # a new proposal replaces the previous unapproved one
    ex("DELETE FROM tasks WHERE room_id=? AND status='proposed'", (room_id,))
    ex("DELETE FROM contracts WHERE room_id=? AND status='proposed'", (room_id,))
    contract_ids: dict[str, int] = {}
    for c in plan.contracts:
        last = q1(
            "SELECT MAX(version) v FROM contracts WHERE room_id=? AND name=?", (room_id, c.name)
        )
        contract_ids[c.name] = ex(
            "INSERT INTO contracts(room_id,kind,name,content,version,status,spec_item_ids,created) "
            "VALUES(?,?,?,?,?,'proposed',?,?)",
            (
                room_id,
                c.kind,
                c.name,
                c.content,
                int((last or {}).get("v") or 0) + 1,
                json.dumps(sorted(set(c.spec_item_ids) & spec_ids)),
                now(),
            ),
        )
    for t in plan.tasks:
        pinned = [contract_ids[n] for n in t.contracts if n in contract_ids]
        pinned += [
            r["id"]
            for n in t.contracts
            if n not in contract_ids
            for r in q(
                "SELECT id FROM contracts WHERE room_id=? AND name=? AND status='approved' "
                "ORDER BY version DESC LIMIT 1",
                (room_id, n),
            )
        ]
        ex(
            "INSERT INTO tasks(room_id,key,title,description,component,depends_on,suggested_owner,"
            "owner_member_id,status,spec_item_ids,contract_ids,created) "
            "VALUES(?,?,?,?,?,?,?,?,'proposed',?,?,?)",
            (
                room_id,
                t.key,
                t.title,
                t.description,
                t.component,
                json.dumps(t.depends_on),
                t.suggested_owner,
                by_name.get((t.suggested_owner or "").lower()),
                json.dumps(sorted(set(t.spec_item_ids) & spec_ids)),
                json.dumps(pinned),
                now(),
            ),
        )
    return {"tasks": tasks(room_id), "contracts": contracts(room_id), "build_order": order}


def update_task(task_id: int, changes: dict[str, Any]) -> dict[str, Any]:
    """Edit a proposed task (owner, title, description, component, dependencies)."""
    t = task(task_id)
    if t["status"] != "proposed":
        raise PlanError("only proposed tasks can be edited; approved plans are fixed")
    allowed = {"owner_member_id", "title", "description", "component", "depends_on"}
    bad = set(changes) - allowed
    if bad:
        raise PlanError(f"cannot change: {', '.join(sorted(bad))}")
    owner = changes.get("owner_member_id")
    if owner is not None and not q1(
        "SELECT 1 x FROM members WHERE id=? AND room_id=? AND role!='viewer'", (owner, t["room_id"])
    ):
        raise PlanError("the owner must be a member (not a viewer) of this workspace")
    if "depends_on" in changes:
        deps = {r["key"]: r["depends_on"] for r in tasks(t["room_id"])}
        deps[t["key"]] = list(changes["depends_on"])
        check_acyclic(deps)
        changes = {**changes, "depends_on": json.dumps(list(changes["depends_on"]))}
    for col, value in changes.items():
        ex(f"UPDATE tasks SET {col}=? WHERE id=?", (value, task_id))  # noqa: S608 - col is allow-listed
    return task(task_id)


def approve(room_id: int) -> dict[str, Any]:
    """Approve the proposed plan: contracts become approved (pinned), tasks become approved."""
    proposed = q("SELECT id FROM tasks WHERE room_id=? AND status='proposed'", (room_id,))
    if not proposed:
        raise PlanError("there is no proposed plan to approve")
    check_acyclic({t["key"]: t["depends_on"] for t in tasks(room_id)})
    for c in q("SELECT id, name FROM contracts WHERE room_id=? AND status='proposed'", (room_id,)):
        ex(
            "UPDATE contracts SET status='superseded' WHERE room_id=? AND name=? AND status='approved'",
            (room_id, c["name"]),
        )
        ex("UPDATE contracts SET status='approved' WHERE id=?", (c["id"],))
    ex("UPDATE tasks SET status='approved' WHERE room_id=? AND status='proposed'", (room_id,))
    from app.services import knowledge  # stage 10: trace requirement -> task -> contract

    knowledge.link_plan(room_id)
    return {"tasks": tasks(room_id), "contracts": contracts(room_id)}


def propose_contract_version(
    room_id: int, name: str, kind: str, content: str, member_id: int | None
) -> dict[str, Any]:
    """Contracts are append-only: a change is a new proposed version for the owner to approve."""
    if not KEY_RE.match(name) or kind not in ("api", "schema", "type") or not content.strip():
        raise PlanError("a contract needs a name (letters, digits, - or _), a kind and content")
    last = q1("SELECT MAX(version) v FROM contracts WHERE room_id=? AND name=?", (room_id, name))
    cid = ex(
        "INSERT INTO contracts(room_id,kind,name,content,version,status,created_by,created) "
        "VALUES(?,?,?,?,?,'proposed',?,?)",
        (room_id, kind, name, content, int((last or {}).get("v") or 0) + 1, member_id, now()),
    )
    return _decode(q1("SELECT * FROM contracts WHERE id=?", (cid,)) or {}, "spec_item_ids")


def approve_contract(contract_id: int) -> dict[str, Any]:
    c = q1("SELECT * FROM contracts WHERE id=?", (contract_id,))
    if not c:
        raise LookupError("no such contract")
    if c["status"] != "proposed":
        raise PlanError(f"this contract version is {c['status']}")
    ex(
        "UPDATE contracts SET status='superseded' WHERE room_id=? AND name=? AND status='approved'",
        (c["room_id"], c["name"]),
    )
    ex("UPDATE contracts SET status='approved' WHERE id=?", (contract_id,))
    return _decode(q1("SELECT * FROM contracts WHERE id=?", (contract_id,)) or {}, "spec_item_ids")


def can_start(task_id: int) -> tuple[bool, str]:
    t = task(task_id)
    if t["status"] not in (
        "approved",
        "in_progress",
        "submitted",
    ):  # submitted: a fix after a failed check
        return False, f"the task is {t['status']}: the plan must be approved first"
    for cid in t["contract_ids"]:
        c = q1("SELECT name, version, status FROM contracts WHERE id=?", (cid,))
        if not c or c["status"] == "proposed":
            return False, "a contract this task relies on is not approved yet"
    return True, ""
