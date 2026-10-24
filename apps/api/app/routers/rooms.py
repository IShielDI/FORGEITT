"""Workspace ("room") API: rooms, members and keys, agent catalog, runs, live events, verification,
approval and merge, credits. Business logic lives in app.services; this module only maps HTTP to it."""

import asyncio
import json
import re
import shutil
import threading

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.core import auth, config
from app.core.db import ex, now, q, q1
from app.services import agent_runner, events, gitops, graph, ledger, memory, orchestrator, referee

router = APIRouter()


# ---------- models ----------
class MemberIn(BaseModel):
    name: str
    email: str = ""
    anthropic_key: str | None = None
    key_type: str = "plain"
    contribution: float = 0.0


class RoomIn(BaseModel):
    name: str
    members: list[MemberIn]
    template: str = "sample"  # "sample" (demo shop) or "blank" (start from nothing)


class DecisionIn(BaseModel):
    author: str = ""
    content: str
    part: str | None = None


class RunIn(BaseModel):
    task: str
    model: str | None = None


class RunAsIn(BaseModel):
    agent: str
    task: str
    model: str | None = None
    member_id: int | None = None


class ApproveIn(BaseModel):
    change_ids: list[int]
    approver: str = ""
    allow_inconclusive: bool = False


class AmountIn(BaseModel):
    amount: float
    member_id: int | None = None
    target: int | None = None
    checkpoint_id: int | None = None


class FundIn(BaseModel):
    lender: int | None = None
    amount: float


class ChoiceIn(BaseModel):
    choice: str
    backup_model: str | None = None


class KeyIn(BaseModel):
    anthropic_key: str
    key_type: str = "plain"


class CatalogIn(BaseModel):
    key: str
    label: str
    description: str = ""
    role_prompt: str = ""
    model: str | None = None
    part: str | None = None


class BootstrapIn(BaseModel):
    task: str
    agent: str | None = None


class JourneyIn(BaseModel):
    goal: str
    success_text: str = ""
    db_check: str = ""


class HoldoutIn(BaseModel):
    filename: str
    content: str


def _room(rid):
    r = q1("SELECT * FROM rooms WHERE id=?", (rid,))
    if not r:
        raise HTTPException(404, "room not found")
    return r


def _who(request, rid, claimed=None):
    """The acting member (or None when logins are off and nobody was named). Also checks the room exists."""
    _room(rid)
    return auth.actor(request, rid, claimed)


def _name(m, fallback=""):
    return m["name"] if m else fallback


def _known_model(model):
    if model and not q1("SELECT 1 x FROM prices WHERE model=?", (model,)):
        raise HTTPException(
            400,
            f"no price known for model '{model}': add it to the prices table first so the meter can count it",
        )


def _instance(rid, member):
    """The member's own agent (own workspace, own key, own portion). Created on first use."""
    name = f"{member['name']}-agent"
    ag = q1("SELECT * FROM agents WHERE room_id=? AND name=?", (rid, name))
    if not ag:
        ex(
            "INSERT INTO agents(room_id,name,member_id,part,model) VALUES(?,?,?,?,?)",
            (rid, name, member["id"], None, config.DEFAULT_MODEL),
        )
        ag = q1("SELECT * FROM agents WHERE room_id=? AND name=?", (rid, name))
    return ag


# ---------- rooms ----------
DEFAULT_ROLES = {
    "builder": (
        "Builder",
        "Writes and changes code for a task you describe.",
        "Build what the task asks, in small steps, with tests passing.",
        None,
    ),
    "fixer": (
        "Fixer",
        "Finds and fixes a bug with the smallest change.",
        "Reproduce the problem first, fix the cause (not the symptom), change as little as possible.",
        None,
    ),
}


@router.post("/api/rooms")
def create_room(body: RoomIn):
    if body.template not in ("sample", "blank"):
        raise HTTPException(400, "template must be 'sample' or 'blank'")
    if not body.members:
        raise HTTPException(400, "a room needs at least one member")
    blank = body.template == "blank"
    rid = ex(
        "INSERT INTO rooms(name,created,mode,bootstrapped) VALUES(?,?,?,?)",
        (body.name, now(), body.template, 0 if blank else 1),
    )
    h = gitops.room_dir(rid) / "holdout"
    if blank:
        gitops.init_blank(rid)
        h.mkdir(parents=True, exist_ok=True)  # no hold-out tests until a human writes them
    else:
        gitops.init_original(rid)
        shutil.copytree(config.SAMPLE_HOLDOUT, h)
    mids, tokens = {}, {}
    for i, m in enumerate(body.members):
        tok = auth.new_token()
        tokens[m.name] = tok
        mid = ex(
            "INSERT INTO members(room_id,name,email,token_hash,is_owner) VALUES(?,?,?,?,?)",
            (rid, m.name, m.email, auth.hash_token(tok), 1 if i == 0 else 0),
        )
        mids[m.name] = mid
        if m.anthropic_key:
            ledger.add_key(mid, "anthropic", m.key_type, m.anthropic_key)
        if m.contribution:
            ledger.contribute(rid, mid, m.contribution)
    names = [m.name for m in body.members]
    mp = json.loads((gitops.original(rid) / "protected/contracts/map.json").read_text())
    # sample project: each part is owned by a member (round-robin) and that member's agent starts on that part
    for i, (pname, p) in enumerate(mp["parts"].items()):
        owner = names[i % len(names)]
        ex(
            "INSERT INTO parts(room_id,name,owner,paths,depends_on) VALUES(?,?,?,?,?)",
            (rid, pname, owner, json.dumps(p["paths"]), json.dumps(p["depends_on"])),
        )
        if (
            pname != "qa"
            and not blank
            and not q1("SELECT 1 x FROM agents WHERE room_id=? AND name=?", (rid, f"{owner}-agent"))
        ):
            ex(
                "INSERT INTO agents(room_id,name,member_id,part,model) VALUES(?,?,?,?,?)",
                (rid, f"{owner}-agent", mids[owner], pname, config.DEFAULT_MODEL),
            )
    for n in names:  # every member gets their own agent, whatever the project
        if not q1("SELECT 1 x FROM agents WHERE room_id=? AND name=?", (rid, f"{n}-agent")):
            ex(
                "INSERT INTO agents(room_id,name,member_id,part,model) VALUES(?,?,?,?,?)",
                (rid, f"{n}-agent", mids[n], None, config.DEFAULT_MODEL),
            )
    # the catalog: roles anyone in the workspace can pick (the owner can edit it)
    for key, (label, desc, prompt, part) in DEFAULT_ROLES.items():
        ex(
            "INSERT INTO agent_catalog(room_id,key,label,description,role_prompt,model,part) VALUES(?,?,?,?,?,?,?)",
            (rid, key, label, desc, prompt, config.DEFAULT_MODEL, part),
        )
    if not blank:
        for pname in mp["parts"]:
            if pname != "qa":
                ex(
                    "INSERT INTO agent_catalog(room_id,key,label,description,role_prompt,model,part) VALUES(?,?,?,?,?,?,?)",
                    (
                        rid,
                        pname,
                        pname.capitalize() + " agent",
                        f"Works on the {pname} part only.",
                        f"You focus on the {pname} part.",
                        config.DEFAULT_MODEL,
                        pname,
                    ),
                )
    for c in json.loads(
        (gitops.original(rid) / "protected/contracts/contracts.json").read_text()
    ).items():
        memory.add(rid, "contract", "platform", f"{c[0]}: {c[1]}", by_platform=True)
    return {
        "id": rid,
        "members": [
            {"id": mids[n], "name": n, "token": tokens[n], "is_owner": n == names[0]} for n in names
        ],
        "note": "Each token is shown once. Keep it: it is your login for this workspace.",
    }


@router.get("/api/rooms")
def rooms():
    return (
        q("SELECT id,name,mode,bootstrapped,created FROM rooms ORDER BY id DESC")
        if not config.REQUIRE_AUTH
        else []
    )  # no listing when logins are on


@router.get("/api/rooms/{rid}")
def room(rid: int, request: Request, member: int | None = None):
    r = _room(rid)
    me = _who(request, rid, member) or {}
    members = q("SELECT id,name,email,is_owner FROM members WHERE room_id=?", (rid,))
    view_member = me.get("id") or member or members[0]["id"]
    return {
        "room": r,
        "members": members,
        "agents": q(
            "SELECT id,name,member_id,part,model,status,steps,note FROM agents WHERE room_id=?",
            (rid,),
        ),
        "map": graph.system_map(rid),
        "budget": ledger.room_view(rid, view_member),
        "pile": {
            "due": orchestrator.pile_due(rid),
            "size": config.PILE_SIZE,
            "wait_min": config.PILE_WAIT_MIN,
        },
        "sandbox": agent_runner.sandbox_mode(),
        "referee": {
            "tinyfish_key_set": bool(config.TINYFISH_KEY),
            "step_limit": config.STEP_LIMIT,
            "runs_last_hour": orchestrator.referee.runs_last_hour(rid),
            "runs_per_hour_cap": config.RUNS_PER_HOUR,
        },
    }


# ---------- me / connecting an account ----------
@router.get("/api/rooms/{rid}/me")
def me(rid: int, request: Request, member: int | None = None):
    m = _who(request, rid, member)
    if not m:
        raise HTTPException(400, "say who you are (member id)")
    k = q1(
        "SELECT last4,key_type FROM keys WHERE member_id=? AND provider='anthropic' AND status='active' ORDER BY id DESC",
        (m["id"],),
    )
    return {
        "id": m["id"],
        "name": m["name"],
        "is_owner": bool(m["is_owner"]),
        "has_key": bool(k),
        "key_last4": k["last4"] if k else None,
        "key_type": k["key_type"] if k else None,
    }


@router.post("/api/rooms/{rid}/me/key")
def connect_key(rid: int, body: KeyIn, request: Request, member: int | None = None):
    """Connect your own Anthropic API key. It is encrypted at rest and never sent back to any screen."""
    m = _who(request, rid, member)
    if not m:
        raise HTTPException(400, "say who you are (member id)")
    if not body.anthropic_key.startswith("sk-ant-"):
        raise HTTPException(
            400, "that does not look like an Anthropic API key (it starts with sk-ant-)"
        )
    if body.key_type not in ("plain", "capped"):
        raise HTTPException(400, "key_type must be 'plain' or 'capped'")
    ex("UPDATE keys SET status='replaced' WHERE member_id=? AND provider='anthropic'", (m["id"],))
    ledger.add_key(m["id"], "anthropic", body.key_type, body.anthropic_key)
    return {"connected": True, "key_last4": body.anthropic_key[-4:]}


# ---------- discussion / split ----------
@router.post("/api/rooms/{rid}/memory")
def add_decision(rid: int, body: DecisionIn, request: Request):
    m = _who(request, rid)
    return {
        "id": memory.add(
            rid, "decision", _name(m, body.author or "member"), body.content, part=body.part
        )
    }


@router.get("/api/rooms/{rid}/memory")
def get_memory(rid: int, request: Request, kind: str | None = None):
    _who(request, rid)
    return memory.listing(rid, kind)


@router.post("/api/rooms/{rid}/split")
def split(rid: int, request: Request):
    _who(request, rid)
    return {
        "parts": graph.parts(rid),
        "build_order": graph.build_order(rid),
        "contracts": json.loads(
            (gitops.original(rid) / "protected/contracts/contracts.json").read_text()
        ),
    }


@router.post("/api/rooms/{rid}/contract-changes/{mid}/approve")
def approve_cc(rid: int, mid: int, request: Request, approver: str = ""):
    m = _who(request, rid)
    req = q1("SELECT * FROM memory WHERE id=? AND room_id=? AND kind='contract-change'", (mid, rid))
    if not req:
        raise HTTPException(404, "no such request")
    if config.REQUIRE_AUTH and not m["is_owner"]:
        owner = graph.owner_of(rid, req["part"]) if req["part"] else None
        if owner != m["name"]:
            raise HTTPException(
                403, "only the part's owner or the workspace owner can approve a contract change"
            )
    return {"contract_id": memory.approve_contract_change(rid, mid, _name(m, approver))}


@router.get("/api/models")
def models():
    return [
        r["model"] for r in q("SELECT model FROM prices ORDER BY input")
    ]  # models the meter has a price for


# ---------- agent catalog ----------
@router.get("/api/rooms/{rid}/catalog")
def catalog(rid: int, request: Request):
    _who(request, rid)
    return q(
        "SELECT key,label,description,role_prompt,model,part FROM agent_catalog WHERE room_id=? ORDER BY id",
        (rid,),
    )


@router.put("/api/rooms/{rid}/catalog")
def catalog_put(rid: int, body: CatalogIn, request: Request):
    _room(rid)
    auth.owner(request, rid) if config.REQUIRE_AUTH else None
    if not re.fullmatch(r"[a-z0-9_-]{1,30}", body.key):
        raise HTTPException(400, "key: lowercase letters, digits, - or _")
    _known_model(body.model)
    ex(
        "INSERT INTO agent_catalog(room_id,key,label,description,role_prompt,model,part) VALUES(?,?,?,?,?,?,?) "
        "ON CONFLICT(room_id,key) DO UPDATE SET label=excluded.label, description=excluded.description, role_prompt=excluded.role_prompt, model=excluded.model, part=excluded.part",
        (
            rid,
            body.key,
            body.label,
            body.description,
            body.role_prompt,
            body.model or config.DEFAULT_MODEL,
            body.part,
        ),
    )
    return {"saved": body.key}


@router.delete("/api/rooms/{rid}/catalog/{key}")
def catalog_delete(rid: int, key: str, request: Request):
    _room(rid)
    auth.owner(request, rid) if config.REQUIRE_AUTH else None
    ex("DELETE FROM agent_catalog WHERE room_id=? AND key=?", (rid, key))
    return {"deleted": key}


# ---------- running agents ----------
def _guard_blank(rid):
    r = _room(rid)
    if r["mode"] == "blank" and not r["bootstrapped"]:
        raise HTTPException(
            409, "this project has no approved baseline yet: run the bootstrap first and approve it"
        )


def _execute(rid, name, task, role, bootstrap):
    """Run one agent task to the end, queue its change for checking, and tell the live stream how it went."""
    try:
        res = agent_runner.run_task(
            rid,
            name,
            task,
            summary=("Bootstrap: " if bootstrap else "") + task[:100],
            bootstrap=bootstrap,
            role=role,
        )
        if res["change_id"]:
            res["change"] = orchestrator.submit_change(rid, res["change_id"])
        events.emit(
            rid,
            name,
            "finished",
            {
                "status": res["status"],
                "steps": res["steps"],
                "change_id": res["change_id"],
                "change_status": (res.get("change") or {}).get("status"),
                "note": res["final_text"][:400],
            },
        )
        return res
    except Exception as e:
        ex("UPDATE agents SET status='error' WHERE room_id=? AND name=?", (rid, name))
        events.emit(rid, name, "finished", {"status": "error", "note": f"{type(e).__name__}: {e}"})
        raise


def _start(rid, name, task, role, bootstrap, wait):
    ag = q1("SELECT status FROM agents WHERE room_id=? AND name=?", (rid, name))
    if ag["status"] == "running":
        raise HTTPException(409, "this agent is already working on a task: wait for it or stop it")
    ex("UPDATE agents SET status='running' WHERE room_id=? AND name=?", (rid, name))
    if wait:
        return _execute(rid, name, task, role, bootstrap)
    threading.Thread(
        target=lambda: _safe_exec(rid, name, task, role, bootstrap), daemon=True
    ).start()
    return {"accepted": True, "agent": name}


def _safe_exec(*a):
    try:
        _execute(*a)
    except Exception as e:
        print("agent run failed:", e)


@router.post("/api/rooms/{rid}/run")
def run_picked(rid: int, body: RunAsIn, request: Request, wait: bool = False):
    """Pick an agent from the workspace catalog and give it a task. It runs as YOU: your workspace, your key, your portion.
    In a blank project the first task is automatically the bootstrap."""
    m = _who(request, rid, body.member_id)
    if not m:
        raise HTTPException(400, "say who you are (member_id)")
    e = q1("SELECT * FROM agent_catalog WHERE room_id=? AND key=?", (rid, body.agent))
    if not e:
        raise HTTPException(404, "that agent is not in this workspace's catalog")
    _known_model(body.model)
    r = _room(rid)
    boot = r["mode"] == "blank" and not r["bootstrapped"]
    ag = _instance(rid, m)
    ex(
        "UPDATE agents SET part=?, model=?, role=? WHERE id=?",
        (e["part"], body.model or e["model"] or config.DEFAULT_MODEL, e["key"], ag["id"]),
    )
    role = {"key": e["key"], "label": e["label"], "prompt": e["role_prompt"], "part": e["part"]}
    return _start(rid, ag["name"], body.task, role, boot, wait)


@router.post("/api/rooms/{rid}/agents/{name}/run")
def run_agent(rid: int, name: str, body: RunIn, request: Request, wait: bool = True):
    """Run a named agent instance directly (kept for scripts and tests). It must be yours."""
    ag = q1("SELECT * FROM agents WHERE room_id=? AND name=?", (rid, name))
    if not ag:
        raise HTTPException(404, "no such agent")
    _who(request, rid, ag["member_id"])
    _guard_blank(rid)
    _known_model(body.model)
    if body.model:
        ex("UPDATE agents SET model=? WHERE id=?", (body.model, ag["id"]))
    return _start(rid, name, body.task, None, False, wait)


@router.post("/api/rooms/{rid}/bootstrap")
def bootstrap(rid: int, body: BootstrapIn, request: Request, wait: bool = True):
    """First step of a blank project: an agent writes the spec, the tests and the first app. A human then reviews and
    approves; that approval is what turns it into the locked original."""
    r = _room(rid)
    if r["mode"] != "blank":
        raise HTTPException(400, "only blank projects have a bootstrap step")
    if r["bootstrapped"]:
        raise HTTPException(400, "already bootstrapped")
    name = body.agent or (
        q1("SELECT name FROM agents WHERE room_id=? ORDER BY id", (rid,)) or {}
    ).get("name")
    ag = q1("SELECT * FROM agents WHERE room_id=? AND name=?", (rid, name)) if name else None
    if not ag:
        raise HTTPException(404, "no such agent")
    _who(request, rid, ag["member_id"])
    return _start(rid, name, body.task, None, True, wait)


@router.post("/api/rooms/{rid}/agents/{name}/stop")
def stop_agent(rid: int, name: str, request: Request):
    ag = q1("SELECT * FROM agents WHERE room_id=? AND name=?", (rid, name))
    if not ag:
        raise HTTPException(404, "no such agent")
    m = _who(request, rid)
    if config.REQUIRE_AUTH and ag["member_id"] != m["id"] and not m["is_owner"]:
        raise HTTPException(403, "only the agent's member or the workspace owner can stop it")
    ex("UPDATE agents SET stop_requested=1 WHERE id=?", (ag["id"],))
    return {"stopping": name}


@router.post("/api/rooms/{rid}/agents/{name}/choice")
def budget_choice(rid: int, name: str, body: ChoiceIn, request: Request):
    """At 90%: request a loan, continue on the backup model, or pause. The person may do two at once."""
    ag = q1("SELECT * FROM agents WHERE room_id=? AND name=?", (rid, name))
    if not ag:
        raise HTTPException(404, "no such agent")
    _who(request, rid, ag["member_id"])
    _known_model(body.backup_model)
    if body.choice == "backup":
        ex(
            "UPDATE agents SET using_backup=1, backup_model=COALESCE(?,backup_model) WHERE room_id=? AND name=?",
            (body.backup_model, rid, name),
        )
    elif body.choice == "pause":
        ex("UPDATE agents SET status='paused' WHERE room_id=? AND name=?", (rid, name))
    elif body.choice == "primary":
        ex("UPDATE agents SET using_backup=0 WHERE room_id=? AND name=?", (rid, name))
    return q1(
        "SELECT id,name,member_id,part,model,backup_model,using_backup,status FROM agents WHERE room_id=? AND name=?",
        (rid, name),
    )


# ---------- live progress ----------
@router.get("/api/rooms/{rid}/events/list")
def events_list(rid: int, request: Request, after: int = 0):
    _who(request, rid)
    return events.since(rid, after)


@router.get("/api/rooms/{rid}/events")
async def events_stream(rid: int, request: Request, after: int = 0):
    """Server-sent events: what the agents are doing right now. Reconnect with ?after=<last id> to resume."""
    _who(request, rid)

    async def gen():
        last = after
        while not await request.is_disconnected():
            rows = await asyncio.to_thread(events.since, rid, last)
            for r in rows:
                last = r["id"]
                yield f"id: {r['id']}\ndata: {json.dumps(r)}\n\n"
            if not rows:
                yield ": keep-alive\n\n"
            await asyncio.sleep(0.7)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------- blank projects: journey, hidden tests ----------
@router.put("/api/rooms/{rid}/journey")
def set_journey(rid: int, body: JourneyIn, request: Request):
    """The customer journey the referee replays, in plain words, written by a human. Stored outside the repo."""
    _room(rid)
    auth.owner(request, rid) if config.REQUIRE_AUTH else None
    try:
        return referee.save_journey(rid, body.goal, body.success_text, body.db_check)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/api/rooms/{rid}/journey")
def get_journey(rid: int, request: Request):
    _who(request, rid)
    return referee.load_journey(rid) or {}


@router.post("/api/rooms/{rid}/holdout")
def add_holdout(rid: int, body: HoldoutIn, request: Request):
    """A human adds a hidden test. It lives in the room's hold-out folder, runs only in the mirror, never reaches an agent."""
    _room(rid)
    auth.owner(request, rid) if config.REQUIRE_AUTH else None
    if not re.fullmatch(r"test_[A-Za-z0-9_]{1,60}\.py", body.filename):
        raise HTTPException(400, "file name must look like test_something.py")
    d = gitops.room_dir(rid) / "holdout"
    d.mkdir(parents=True, exist_ok=True)
    (d / body.filename).write_text(body.content)
    return {"saved": body.filename}


@router.get("/api/rooms/{rid}/holdout")
def list_holdout(rid: int, request: Request):
    _who(request, rid)
    d = gitops.room_dir(rid) / "holdout"
    return (
        sorted(p.name for p in d.glob("test_*.py")) if d.exists() else []
    )  # names only: contents are never served


# ---------- changes / referee / merge ----------
def _change(c):
    if c:
        c["evidence"] = json.loads(c["evidence"] or "{}")
    return c


@router.get("/api/rooms/{rid}/changes")
def changes(rid: int, request: Request):
    _who(request, rid)
    return [
        _change(c) | {"evidence": None}
        for c in q("SELECT * FROM changes WHERE room_id=? ORDER BY id DESC", (rid,))
    ]


@router.get("/api/changes/{cid}")
def change(cid: int, request: Request):
    c = q1("SELECT * FROM changes WHERE id=?", (cid,))
    if not c:
        raise HTTPException(404)
    _who(request, c["room_id"])
    c = _change(c)
    c["attempts"] = q(
        "SELECT * FROM attempts WHERE room_id=? AND agent=? ORDER BY id", (c["room_id"], c["agent"])
    )
    return c


@router.post("/api/rooms/{rid}/referee/run")
def referee_run(rid: int, request: Request, force: bool = True):
    _who(request, rid)
    return orchestrator.run_referee(rid, force=force) or {
        "skipped": "nothing ready or pile not due"
    }


@router.post("/api/rooms/{rid}/approve")
def approve(rid: int, body: ApproveIn, request: Request):
    m = auth.owner(request, rid) if config.REQUIRE_AUTH else _who(request, rid)
    try:
        return orchestrator.approve(
            rid, body.change_ids, _name(m, body.approver or "human"), body.allow_inconclusive
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/api/rooms/{rid}/undo/{mid}")
def undo(rid: int, mid: int, request: Request):
    auth.owner(request, rid) if config.REQUIRE_AUTH else _who(request, rid)
    try:
        return orchestrator.undo(rid, mid)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.get("/api/rooms/{rid}/merges")
def merges(rid: int, request: Request):
    _who(request, rid)
    return q("SELECT * FROM merges WHERE room_id=? ORDER BY id DESC", (rid,))


@router.get("/api/rooms/{rid}/attempts")
def attempts(rid: int, request: Request):
    _who(request, rid)
    return q("SELECT * FROM attempts WHERE room_id=? ORDER BY id DESC", (rid,))


@router.get("/api/evidence/{rid}/{batch}/{path:path}")
def evidence_file(rid: int, batch: str, path: str, request: Request):
    _who(request, rid)
    base = (gitops.room_dir(rid) / "evidence" / batch).resolve()
    f = (base / path).resolve()
    if base not in f.parents or not f.is_file():
        raise HTTPException(404)
    return FileResponse(f)


# ---------- budget: ledger, requests, loans ----------
@router.get("/api/rooms/{rid}/budget")
def budget(rid: int, request: Request, member: int | None = None):
    m = _who(request, rid, member)
    if not m:
        raise HTTPException(400, "say who you are (member id)")
    member = m["id"]
    ledger.housekeeping(rid)
    return {
        "view": ledger.room_view(rid, member),
        "requests": ledger.visible_requests(rid, member),
        "loans": q(
            "SELECT * FROM loans WHERE room_id=? AND (lender=? OR borrower=?) ORDER BY id DESC",
            (rid, member, member),
        ),
        "checkpoints": q(
            "SELECT * FROM checkpoints WHERE room_id=? AND member_id=? ORDER BY id", (rid, member)
        ),
        "recent": q(
            "SELECT agent,model,cost,tin,tout,ts FROM ledger WHERE room_id=? AND member_id=? ORDER BY id DESC LIMIT 20",
            (rid, member),
        ),
    }


@router.post("/api/rooms/{rid}/contribute")
def contribute(rid: int, body: AmountIn, request: Request):
    m = _who(request, rid, body.member_id)
    if not m or body.amount <= 0:
        raise HTTPException(400, "say who you are and a positive amount")
    return {"id": ledger.contribute(rid, m["id"], body.amount)}


@router.post("/api/rooms/{rid}/requests")
def make_request(rid: int, body: AmountIn, request: Request):
    m = _who(request, rid, body.member_id)
    if not m:
        raise HTTPException(400, "say who you are (member_id)")
    try:
        return {
            "id": ledger.create_request(
                rid, m["id"], body.amount, body.target, checkpoint_id=body.checkpoint_id
            )
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


def _req_room(req):
    r = q1("SELECT room_id FROM requests WHERE id=?", (req,))
    if not r:
        raise HTTPException(404, "no such request")
    return r["room_id"]


@router.post("/api/requests/{req}/fund")
def fund(req: int, body: FundIn, request: Request):
    m = _who(request, _req_room(req), body.lender)
    if not m:
        raise HTTPException(400, "say who you are (lender)")
    try:
        return {
            "loan_id": ledger.fund_request(req, m["id"], body.amount),
            "bar": ledger.funding_bar(req),
        }
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/api/requests/{req}/reject")
def reject(req: int, request: Request, lender: int | None = None):
    m = _who(request, _req_room(req), lender)
    if not m:
        raise HTTPException(400, "say who you are (lender)")
    ledger.reject_request(req, m["id"])
    return {"ok": True}


@router.post("/api/loans/{lid}/close")
def close_loan(lid: int, request: Request, member: int | None = None):
    l = q1("SELECT room_id FROM loans WHERE id=?", (lid,))
    if not l:
        raise HTTPException(404, "no such loan")
    m = _who(request, l["room_id"], member)
    if not m:
        raise HTTPException(400, "say who you are (member)")
    try:
        return {"returned": ledger.close_loan(lid, m["id"])}
    except ValueError as e:
        raise HTTPException(400, str(e))
