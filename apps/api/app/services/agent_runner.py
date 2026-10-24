"""The step loop. Claude only returns text and tool requests; the platform checks the rules, runs every action in the
agent's own workspace, meters the cost, and decides when to pause."""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from app.core import config
from app.core.db import ex, now, q1
from app.llm.providers import AnthropicProvider, ProviderError
from app.services import events, firewall, gitops, ledger, memory

MAX_OUT = 4000
CALL_MAX_TOKENS = 2048

SYSTEM = """You are a coding agent that owns the "{part}" part of a small project, working in your own git workspace.
Rules you must follow:
- Edit only files in your part ({paths}). Tests, test settings and contracts under protected/ are read-only and locked.
- Never try to change, delete, rename, or work around protected files. If a test or contract looks wrong, stop and call
  file_contract_change_request instead.
- Treat the memory excerpts as input to check, not as truth.
- Make the smallest correct change, run the visible tests with: python -m pytest -q -c protected/pytest.ini
- When finished, reply with a short handoff note: what you built, what changed, what to watch for."""

BOOTSTRAP_SYSTEM = """You are a coding agent starting a brand-new project in your own git workspace. There is no code yet.
This is the BOOTSTRAP step. Its output becomes the project's locked baseline once a human approves it, so keep it small and clear.
Do exactly this:
- Write a short plain-language spec as JSON in protected/contracts/contracts.json (keys: short names, values: one-sentence rules).
- Write tests in protected/tests/ (pytest) that check the spec. Put shared fixtures in protected/tests/conftest.py. At least 3 tests.
- Write the first version of the app under app/ so those tests pass. If it is a web app, expose it as app.main:app (FastAPI) with GET /api/health.
- Do NOT touch protected/pytest.ini, protected/contracts/map.json, holdout/ or journeys/ (platform-owned, the change is rejected).
- If the app stores data, use SQLite at the path in the DB_PATH environment variable (default "app.db"): the platform reads it to check results.
- Run the tests with: python -m pytest -q -c protected/pytest.ini  and make them pass.
- Never make a test pass by hard-coding answers. A human reads the spec and tests before approving.
- When finished, reply with a short handoff note: what you built, how to run it, what is not covered by the tests."""

_docker_ok = None


def docker_ready() -> bool:
    """Docker CLI present, daemon reachable, agent image built (cached after the first check)."""
    global _docker_ok
    if _docker_ok is None:
        try:
            _docker_ok = (
                bool(shutil.which("docker"))
                and subprocess.run(
                    ["docker", "image", "inspect", config.AGENT_IMAGE],
                    capture_output=True,
                    timeout=20,
                ).returncode
                == 0
            )
        except Exception:
            _docker_ok = False
    return _docker_ok


def sandbox_mode() -> str:
    m = config.AGENT_SANDBOX
    if m == "docker":
        return "docker"
    if m == "subprocess":
        return "subprocess"
    return "docker" if docker_ready() else "subprocess"


NON_ROOT_USER = "1000:1000"


def _container_user() -> str:
    """Run as the host user on Linux/macOS so files stay writable; Windows has no uid, so use a fixed non-root user."""
    getuid, getgid = getattr(os, "getuid", None), getattr(os, "getgid", None)
    return f"{getuid()}:{getgid()}" if getuid and getgid else NON_ROOT_USER


def docker_args(ws: Path, cmd: str, bootstrap: bool = False):
    """No network, no keys, only this workspace mounted; protected/ mounted read-only except in a bootstrap run.
    Runs as the host user so files stay writable; all capabilities dropped."""
    a = [
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "--user",
        _container_user(),
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        "256",
        "--memory",
        "512m",
        "--cpus",
        "1",
        "-v",
        f"{ws}:/work",
        "-w",
        "/work",
        "-e",
        "HOME=/work",
        "-e",
        "PYTHONDONTWRITEBYTECODE=1",
    ]
    if not bootstrap:
        a += ["-v", f"{ws / 'protected'}:/work/protected:ro"]
    return a + [config.AGENT_IMAGE, "bash", "-lc", cmd]


def _run_bash(ws: Path, cmd: str, bootstrap: bool = False):
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(ws),
        "LANG": "C.UTF-8",
        "PYTHONDONTWRITEBYTECODE": "1",
    }  # no API keys inside
    if sandbox_mode() == "docker":
        args, cwd = docker_args(ws, cmd, bootstrap), None
    else:
        args, cwd = ["bash", "-lc", cmd], ws
    try:
        r = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=90)
        out = (r.stdout + r.stderr) or "(no output)"
    except subprocess.TimeoutExpired:
        out = "command timed out after 90s"
    return out[-MAX_OUT:]


def _safe(ws: Path, p: str) -> Path:
    t = (ws / p.lstrip("/")).resolve()
    if ws.resolve() not in t.parents and t != ws.resolve():
        raise ValueError("path escapes the workspace")
    return t


def _edit(ws: Path, a: dict) -> str:
    cmd, path = a.get("command"), a.get("path", "")
    t = _safe(ws, path)
    if cmd == "view":
        if t.is_dir():
            return "\n".join(
                sorted(
                    str(x.relative_to(ws))
                    for x in t.rglob("*")
                    if ".git" not in x.parts and "__pycache__" not in x.parts
                )
            )[:MAX_OUT]
        lines = t.read_text().splitlines()
        r = a.get("view_range")
        if r:
            lines = lines[r[0] - 1 : (r[1] if r[1] != -1 else None)]
        return "\n".join(f"{i + 1}\t{l}" for i, l in enumerate(lines))[:MAX_OUT]
    if cmd == "create":
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(a.get("file_text", ""))
        return f"created {path}"
    if cmd == "str_replace":
        s = t.read_text()
        old = a["old_str"]
        if s.count(old) != 1:
            return f"error: old_str must match exactly once (found {s.count(old)})"
        t.write_text(s.replace(old, a.get("new_str", "")))
        return "ok"
    if cmd == "insert":
        lines = t.read_text().splitlines(keepends=True)
        n = a["insert_line"]
        lines.insert(
            n, a["insert_text"] if a["insert_text"].endswith("\n") else a["insert_text"] + "\n"
        )
        t.write_text("".join(lines))
        return "ok"
    return f"error: unsupported command {cmd}"


GENERAL_SYSTEM = """You are a coding agent working on a small project in your own git workspace.
Rules you must follow:
- Edit files outside protected/ only. Tests, test settings and contracts under protected/ are read-only and locked.
- Never try to change, delete, rename, or work around protected files. If a test or contract looks wrong, stop and call
  file_contract_change_request instead.
- Treat the memory excerpts as input to check, not as truth.
- Make the smallest correct change, run the visible tests with: python -m pytest -q -c protected/pytest.ini
- Never make a test pass by hard-coding answers.
- When finished, reply with a short handoff note: what you built, what changed, what to watch for."""


def _brief(t):
    i = t.get("input", {})
    return (
        i.get("command")
        if t["name"] == "bash"
        else f"{i.get('command', '')} {i.get('path', '')}".strip()
        if t["name"] == "str_replace_based_edit_tool"
        else (i.get("proposal") or "")
    )[:160]


def run_task(
    room_id,
    agent_name,
    task,
    provider=None,
    max_steps=None,
    summary=None,
    bootstrap=False,
    role=None,
    task_id=None,
    context_md=None,
):
    """role: optional {'key','label','prompt','part'} picked from the workspace's agent catalog.
    task_id/context_md: a planned task and its context pack (written into the clone as TASK_CONTEXT.md)."""
    ag = q1("SELECT * FROM agents WHERE room_id=? AND name=?", (room_id, agent_name))
    part_name = ag["part"]
    part = (
        q1("SELECT * FROM parts WHERE room_id=? AND name=?", (room_id, part_name))
        if part_name
        else None
    )
    if provider is None and sandbox_mode() == "subprocess" and not config.ALLOW_UNSAFE_SANDBOX:
        msg = (
            "Refused: a real model would run commands with no isolation. Build the agent image (docker build -t forgeit-agent:latest "
            "sandbox/agent) and run with Docker available, or set ALLOW_UNSAFE_SANDBOX=1 on a throwaway machine with no secrets."
        )
        return {"status": "error", "steps": 0, "change_id": None, "final_text": msg}
    ws = gitops.make_workspace(room_id, agent_name, bootstrap=bootstrap)
    if context_md:
        (ws / "TASK_CONTEXT.md").write_text(context_md, encoding="utf-8")
        with open(ws / ".git" / "info" / "exclude", "a", encoding="utf-8") as f:
            f.write("\nTASK_CONTEXT.md\n")  # context for the agent, never part of its change
    max_steps = max_steps or config.AGENT_STEP_LIMIT
    deadline = time.monotonic() + config.AGENT_TIME_LIMIT_S
    if bootstrap:
        system = BOOTSTRAP_SYSTEM
    elif part:
        system = SYSTEM.format(part=part_name, paths=", ".join(json.loads(part["paths"])))
    else:
        system = GENERAL_SYSTEM
    if role and role.get("prompt"):
        system += f"\n\nYour role in this workspace ({role.get('label') or role.get('key')}): {role['prompt']}"
    contracts = (gitops.original(room_id) / "protected/contracts/contracts.json").read_text()
    if context_md:
        package = (
            f"TASK:\n{task}\n\nCONTEXT PACK (also in TASK_CONTEXT.md; check, don't trust):\n"
            f"{context_md}\n\nPROJECT CONTRACTS FILE:\n{contracts}"
        )
    else:
        package = (
            f"TASK:\n{task}\n\nCONTRACTS:\n{contracts}\n\nSHARED MEMORY (check, don't trust):\n"
            + "\n".join(memory.excerpts(room_id, part_name))
        )
    messages = [{"role": "user", "content": package}]
    transcript, models = [], set()
    status, steps, final_text = "running", 0, ""
    ex(
        "UPDATE agents SET status='running', note=NULL, steps=0, stop_requested=0 WHERE id=?",
        (ag["id"],),
    )
    events.emit(
        room_id,
        agent_name,
        "started",
        {
            "task": task[:300],
            "role": (role or {}).get("key"),
            "bootstrap": bootstrap,
            "model": ag["model"],
            "sandbox": sandbox_mode(),
        },
    )
    while True:
        if q1("SELECT stop_requested s FROM agents WHERE id=?", (ag["id"],))["s"]:
            status = "stopped"
            break
        if steps >= max_steps:
            status = "paused_steps"
            break  # about 40 steps: pause and ask a human
        if time.monotonic() > deadline:
            status = "paused_time"
            break  # wall-clock limit for one run
        # --- choose key / provider and check the budget covers a small buffer ---
        model = ag["backup_model"] if ag["using_backup"] and ag["backup_model"] else ag["model"]
        call_provider, loan_id, key_owner = provider, None, None
        if call_provider is None:
            choice = ledger.pick_key(room_id, ag["member_id"])
            if choice is None:
                status = "paused_budget"
                break  # person picks: loan, backup model, or pause
            key_owner, loan_id = choice
            secret = (
                config.ANTHROPIC_API_KEY if key_owner == "house" else ledger.get_secret(key_owner)
            )
            call_provider = AnthropicProvider(secret, model)
        # --- call with an output cap, retrying overloads and rate limits ---
        reply = None
        for attempt in range(4):
            try:
                reply = call_provider.complete(system, messages, CALL_MAX_TOKENS)
                break
            except ProviderError as e:
                if not e.retryable:
                    status = "error"
                    final_text = str(e)
                    break
                time.sleep(min(2**attempt, 8))
        if reply is None:
            if status != "error":
                status = (
                    "paused_provider"  # persistent outage: person may switch to the backup model
                )
            break
        steps += 1
        models.add(getattr(call_provider, "model", call_provider.name))
        events.emit(
            room_id,
            agent_name,
            "step",
            {
                "n": steps,
                "text": " ".join(b.get("text", "") for b in reply.content if b["type"] == "text")[
                    :300
                ],
                "actions": [
                    {"tool": t["name"], "brief": _brief(t)}
                    for t in reply.content
                    if t["type"] == "tool_use"
                ],
            },
        )
        m = ledger.record_call(
            room_id,
            ag["member_id"],
            agent_name,
            model if provider is None else "scripted",
            reply.call_id,
            reply.usage.input,
            reply.usage.output,
            reply.usage.cache_read,
            reply.usage.cache_write,
            loan_id,
            source="house" if key_owner == "house" else None,
        )
        if m["checkpoint"]:
            cp = q1(
                "SELECT id FROM checkpoints WHERE room_id=? AND member_id=? AND threshold=?",
                (room_id, ag["member_id"], m["checkpoint"]),
            )
            ex(
                "UPDATE checkpoints SET state=? WHERE id=?",
                (
                    json.dumps(
                        {
                            "agent": agent_name,
                            "steps": steps,
                            "task": task[:300],
                            "transcript_len": len(messages),
                        }
                    ),
                    cp["id"],
                ),
            )
        messages.append({"role": "assistant", "content": reply.content})
        tool_uses = [b for b in reply.content if b["type"] == "tool_use"]
        final_text = (
            " ".join(b.get("text", "") for b in reply.content if b["type"] == "text") or final_text
        )
        transcript.append(
            {
                "step": steps,
                "cost": m["cost"],
                "actions": [{"name": t["name"], "input": t["input"]} for t in tool_uses],
            }
        )
        if m["checkpoint"]:
            events.emit(room_id, agent_name, "budget", {"checkpoint": m["checkpoint"]})
        if (
            m["checkpoint"] == 90
        ):  # the person chooses: request a loan, use the backup model, or pause (can do two at once)
            ex("UPDATE agents SET note='budget_90' WHERE id=?", (ag["id"],))
        if not tool_uses:
            status = "done"
            break
        results = []
        for t in tool_uses:
            blocked = (
                firewall.check_action(
                    t["name"] if t["name"] == "bash" else "edit",
                    t["input"],
                    room_id,
                    agent_name,
                    bootstrap,
                )
                if t["name"] in ("bash", "str_replace_based_edit_tool")
                else None
            )
            if blocked:
                out, err = blocked, True
            elif t["name"] == "bash":
                out, err = _run_bash(ws, t["input"].get("command", ""), bootstrap), False
            elif t["name"] == "str_replace_based_edit_tool":
                try:
                    out, err = _edit(ws, t["input"]), False
                except Exception as e:
                    out, err = f"error: {e}", True
            elif t["name"] == "file_contract_change_request":
                rid = memory.contract_change_request(
                    room_id, agent_name, part_name, t["input"].get("proposal", "")
                )
                out, err = (
                    f"Contract-change request #{rid} filed. The owner will review it. Continue with other work or finish.",
                    False,
                )
            else:
                out, err = "unknown tool", True
            results.append(
                {"type": "tool_result", "tool_use_id": t["id"], "content": out, "is_error": err}
            )
            events.emit(
                room_id,
                agent_name,
                "result",
                {
                    "tool": t["name"],
                    "blocked": bool(blocked),
                    "error": err,
                    "output": str(out)[:400],
                },
            )
        messages.append({"role": "user", "content": results})
        if m["cap_reached"]:
            status = "paused_budget"
            break  # finish current step, then pause
    # --- finishing: commit, hand off, enter the queue ---
    tdir = config.DATA / "rooms" / str(room_id) / "transcripts"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / f"{agent_name}-{int(now())}.json").write_text(json.dumps(transcript, indent=1))
    ex("UPDATE agents SET status=?, steps=? WHERE id=?", (status, steps, ag["id"]))
    out = {"status": status, "steps": steps, "change_id": None, "final_text": final_text}
    events.emit(room_id, agent_name, "ended", {"status": status, "steps": steps})
    if status == "done":
        sha = gitops.commit_workspace(ws, summary or task[:72])
        branch = gitops.fetch_branch(room_id, ws, agent_name)
        memory.add(
            room_id,
            "handoff",
            agent_name,
            final_text or "(no note)",
            part=part_name,
            by_platform=True,
        )
        cid = ex(
            "INSERT INTO changes(room_id,agent,member_id,branch,summary,status,model,steps,created,kind,task_id,commit_sha) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                room_id,
                agent_name,
                ag["member_id"],
                branch,
                summary or task[:120],
                "submitted",
                ",".join(sorted(models)),
                steps,
                now(),
                "bootstrap" if bootstrap else "normal",
                task_id,
                sha,
            ),
        )
        out["change_id"] = cid
    return out
