"""Queue -> stacked mirror -> tests -> referee -> human merge. Cheap checks first; the referee runs once on the combined result."""

import json
import uuid
from pathlib import Path

from app.core import config
from app.core.db import ex, now, q, q1
from app.services import firewall, gitops, graph, memory, referee, tunnel
from app.services.mirror import new_mirror


# ---------- failure routing ----------
def route_failure(room, mirror, tests, journey_reason, journey_ran):
    """Simplified trace routing: follow the failing click through the app's own request trace to a handler,
    then to the part that owns it. Only that owner receives the problem."""
    mp = json.loads((gitops.original(room) / "protected/contracts/map.json").read_text())
    part, why = None, None
    failing = [t for t in tests if not t["passed"]]
    if failing:
        f = failing[0]["name"].split("::")[0]
        part = mp["test_to_part"].get(f if f.endswith(".py") else f + ".py") or next(
            (v for k, v in mp["test_to_part"].items() if k.startswith(f)), None
        )
        why = f"failing test {failing[0]['name']}"
    if not part and journey_ran:
        tr = mirror.traces()
        hit = next((t for t in reversed(tr) if t["status"] >= 400), None) or next(
            (t for t in reversed(tr) if t["path"] == "/checkout"), None
        )
        if hit and hit["status"] in (404, 405, 422):
            # 404/405/422: the page sent a request the API does not accept (wrong method, path or fields): the page is wrong, not the API
            part = "frontend"
            why = f"trace: {hit['method']} {hit['path']} -> {hit['status']} (the page issued a request the API does not accept)"
        elif hit:
            part = mp["handler_to_part"].get(hit["handler"])
            why = f"trace: {hit['method']} {hit['path']} -> handler '{hit['handler']}' ({hit['db_writes']} db writes)"
    if not part and len(mp["parts"]) == 1:
        part = next(iter(mp["parts"]))
        why = why or journey_reason
    if not part:
        return None
    p = next(x for x in graph.parts(room) if x["name"] == part)
    return {
        "part": part,
        "owner": p["owner"],
        "why": why,
        "reason": journey_reason,
        "files": p["paths"],
        "retest": graph.affected_by(room, part),
    }


# ---------- submit ----------
def submit_change(room, change_id):
    ch = q1("SELECT * FROM changes WHERE id=?", (change_id,))
    boot = ch.get("kind") == "bootstrap"
    blank = (q1("SELECT mode FROM rooms WHERE id=?", (room,)) or {}).get("mode") == "blank"
    check = firewall.bootstrap_check if boot else firewall.commit_check
    bad = check(str(gitops.original(room)), "main", ch["branch"])
    for b in bad:
        ex(
            "INSERT INTO attempts(room_id,agent,action,path,ts) VALUES(?,?,?,?,?)",
            (room, ch["agent"], f"commit:{b['status']}", b["path"], now()),
        )
    if bad:
        _set(change_id, "rejected_firewall", {"firewall": bad})
        return q1("SELECT * FROM changes WHERE id=?", (change_id,))
    queued = (
        []
        if boot
        else [
            c["branch"]
            for c in q(
                "SELECT branch FROM changes WHERE room_id=? AND status='ready' AND id!=? ORDER BY id",
                (room, change_id),
            )
        ]
    )
    m = new_mirror(room)
    try:
        st = m.merge_stack(queued, ch["branch"])
        if not st["ok"]:
            _set(change_id, "conflict", {"conflict": st})
            return q1("SELECT * FROM changes WHERE id=?", (change_id,))
        t = m.run_tests()
        if boot and not t["tests"]:
            t["passed"] = False
            t["log"] = "bootstrap must include at least one test\n" + t["log"]
        if not t["passed"]:
            routed = route_failure(room, m, t["tests"], "tests failed", False)
            _record_failure(room, routed, change_id)
            _set(change_id, "tests_failed", {"tests": t, "routed": routed})
        elif boot:
            # no hold-out tests and no journey exist yet: a human must read the spec and tests before they become the baseline
            _set(
                change_id,
                "bootstrap_review",
                {
                    "tests": t,
                    "note": "Bootstrap: review the spec and tests, they become the locked original.",
                    "diff": gitops.diff_stat(room, ch["branch"]),
                },
                verdict="needs_human_review",
            )
        elif blank and not referee.load_journey(room):
            # blank projects have no customer journey yet, so this is tests-only verification; the label says so
            _set(
                change_id,
                "passed",
                {
                    "tests": t,
                    "referee": {
                        "verdict": "not_run",
                        "reason": "no customer journey defined for this project yet; verified by the locked tests only",
                    },
                    "diff": gitops.diff_stat(room, ch["branch"]),
                },
                verdict="tests_only",
            )
        else:
            _set(change_id, "ready", {"tests": t})
            ex("UPDATE changes SET ready_at=? WHERE id=?", (now(), change_id))
    finally:
        m.destroy()
    return q1("SELECT * FROM changes WHERE id=?", (change_id,))


def _set(change_id, status, evidence_add=None, verdict=None):
    ch = q1("SELECT evidence FROM changes WHERE id=?", (change_id,))
    ev = json.loads(ch["evidence"] or "{}")
    ev.update(evidence_add or {})
    ex(
        "UPDATE changes SET status=?, evidence=?, verdict=COALESCE(?,verdict) WHERE id=?",
        (status, json.dumps(ev, default=str), verdict, change_id),
    )


def _record_failure(room, routed, change_id):
    if routed:
        memory.add(
            room,
            "failure",
            "platform",
            {"state": "failing", "change": change_id, **routed},
            part=routed["part"],
            by_platform=True,
        )


# ---------- referee ----------
def pile_due(room: int) -> bool:
    ready = q("SELECT * FROM changes WHERE room_id=? AND status='ready' ORDER BY id", (room,))
    if not ready:
        return False
    return (
        len(ready) >= config.PILE_SIZE
        or now() - min(c["ready_at"] or now() for c in ready) >= config.PILE_WAIT_MIN * 60
    )


def _check(room, branches, batch_dir: Path, label):
    """One referee check: fresh mirror, public address, journey, verdict, teardown. Always deletes the mirror and closes the tunnel."""
    m = new_mirror(room)
    tun = None
    out = {"label": label, "branches": branches}
    try:
        st = m.merge_stack(branches[:-1], branches[-1]) if branches else {"ok": True}
        if not branches:  # baseline: just the original
            gitops.git(".", "clone", "-q", "--no-local", str(gitops.original(room)), str(m.path))
            m.install_holdout()
        elif not st["ok"]:
            out.update(
                verdict="conflict", reason=f"merge conflict with {st['conflict_with']}", tests=None
            )
            return out
        journey = referee.load_journey(room)
        tests = m.run_tests()
        out["tests"] = tests
        m.start()
        tun = None
        capped = referee.runs_last_hour(room) >= config.RUNS_PER_HOUR
        if config.TINYFISH_KEY and not capped:
            tun = tunnel.open_tunnel(m.port)
            out["tunnel"] = tun.kind
        use_tf = bool(config.TINYFISH_KEY and tun and tun.url and not capped)
        if not use_tf and not config.ALLOW_STANDIN:
            # Never pretend: without a real browser run there is no referee verdict.
            why = (
                "TINYFISH_API_KEY is not set"
                if not config.TINYFISH_KEY
                else f"hourly referee cap reached ({config.RUNS_PER_HOUR})"
                if capped
                else "no public address for the mirror (install cloudflared or set MIRROR_PUBLIC_URL)"
            )
            out.update(
                verdict="not_run", reason=f"Referee did not run: {why}.", runner=None, attempts=[]
            )
            return out
        if not use_tf and journey:
            out.update(
                verdict="not_run",
                reason="Referee did not run: the offline stand-in can only replay the sample shop.",
                runner=None,
                attempts=[],
            )
            return out
        runner = referee.TinyFishRunner() if use_tf else referee.LocalRunner()
        url = tun.url if use_tf else f"http://127.0.0.1:{m.port}"
        out["runner"] = runner.name
        attempts = []
        for n in range(
            2
        ):  # a lost/blocked browser or a suspicious "pass" is repeated once, no more
            email = f"ref{uuid.uuid4().hex[:8]}@example.com"
            ex(
                "INSERT INTO referee_runs(room_id,ts,runner,steps) VALUES(?,?,?,0)",
                (room, now(), runner.name),
            )
            rr = runner.run(url, referee.goal_for(journey, email), config.STEP_LIMIT)
            runner.collect_evidence(rr, batch_dir / f"{label}-run{n}")
            verdict, reason, suspicious = referee.judge_for(journey, rr, m, email)
            ex(
                "UPDATE referee_runs SET steps=? WHERE id=(SELECT MAX(id) FROM referee_runs)",
                (len(rr.steps),),
            )
            attempts.append(
                {
                    "email": email,
                    "verdict": verdict,
                    "reason": reason,
                    "suspicious": suspicious,
                    "run": rr.asdict(),
                    "orders": m.orders(email) if not journey else [],
                }
            )
            if not (verdict == "browser_failure" or suspicious):
                break
        last = attempts[-1]
        out.update(verdict=last["verdict"], reason=last["reason"], attempts=attempts)
        if last["verdict"] == "browser_failure":
            out["verdict"] = "inconclusive"
            out["reason"] = "Browser failed twice: " + last["reason"]
        failing = [t for t in tests["tests"] if not t["passed"]]
        if (
            out["verdict"] == "pass" and failing
        ):  # journey passed but hidden/visible tests did not: still a failure
            out["verdict"], out["reason"] = (
                "app_failure",
                f"{len(failing)} test(s) failed even though the journey passed",
            )
        if out["verdict"] == "app_failure":
            out["routed"] = route_failure(room, m, tests["tests"], out["reason"], True)
        return out
    finally:
        if tun:
            tun.close()
        m.destroy()


def run_referee(room, force=False):
    ready = q("SELECT * FROM changes WHERE room_id=? AND status='ready' ORDER BY id", (room,))
    if not ready or not (force or pile_due(room)):
        return None
    batch = uuid.uuid4().hex[:8]
    bdir = gitops.room_dir(room) / "evidence" / batch
    bdir.mkdir(parents=True, exist_ok=True)
    for c in ready:
        ex("UPDATE changes SET status='referee' WHERE id=?", (c["id"],))
    branches = [c["branch"] for c in ready]
    res = _check(room, branches, bdir, "combined")
    runs = [res]
    culprit = None
    if res["verdict"] == "not_run":  # put everything back in the queue, with the reason on record
        for c in ready:
            _set(
                c["id"],
                "ready",
                {"referee": {"verdict": "not_run", "reason": res["reason"], "runner": None}},
            )
        return {
            "batch": batch,
            "verdict": "not_run",
            "reason": res["reason"],
            "culprit": None,
            "runs": 0,
        }
    if res["verdict"] == "app_failure" and len(ready) > 1:
        # pick suspects by where the journey failed and which changes touched that area; at most two extra runs per batch
        part = (res.get("routed") or {}).get("part")
        files = (res.get("routed") or {}).get("files", [])

        def touches(c):
            d = gitops.git(
                gitops.original(room), "diff", "--name-only", f"main...{c['branch']}"
            ).stdout.split()
            return any(f.split("#")[0] in d for f in files)

        suspects = sorted(ready, key=lambda c: (not touches(c), -c["id"]))[: config.EXTRA_RUNS_CAP]
        for s in suspects:
            r2 = _check(
                room,
                [b for b in branches if b != s["branch"]],
                bdir,
                f"without-{s['agent']}-{s['id']}",
            )
            runs.append(r2)
            if r2["verdict"] == "pass":
                culprit = s
                break
    for c in ready:
        if res["verdict"] == "pass":
            st = "passed"
        elif res["verdict"] == "inconclusive":
            st = "inconclusive"  # blocks the merge until a human looks
        elif culprit is None:
            st = "referee_failed"  # no single suspect found: back to humans with the evidence
        elif c["id"] == culprit["id"]:
            st = "referee_failed"
        else:
            st = "passed"
        _set(
            c["id"],
            st,
            {
                "batch": batch,
                "referee": {
                    "verdict": res["verdict"],
                    "reason": res["reason"],
                    "runner": res.get("runner"),
                    "tunnel": res.get("tunnel"),
                    "runs": [
                        {k: v for k, v in r.items() if k != "attempts"}
                        | {"attempts": [{**a, "run": a["run"]} for a in r.get("attempts", [])]}
                        for r in runs
                    ],
                    "culprit": culprit["id"] if culprit else None,
                    "routed": res.get("routed"),
                },
                "diff": gitops.diff_stat(room, c["branch"]),
            },
            verdict=res["verdict"],
        )
    if res.get("routed") and (culprit or len(ready) == 1):
        _record_failure(room, res["routed"], (culprit or ready[0])["id"])
    return {
        "batch": batch,
        "verdict": res["verdict"],
        "culprit": culprit["id"] if culprit else None,
        "runs": len(runs),
    }


# ---------- merge / undo ----------
def approve(room, change_ids, approver, allow_inconclusive=False):
    cs = [q1("SELECT * FROM changes WHERE id=? AND room_id=?", (i, room)) for i in change_ids]
    for c in cs:
        ok = c["status"] in ("passed", "bootstrap_review") or (
            allow_inconclusive and c["status"] == "inconclusive"
        )
        if not ok:
            raise ValueError(f"change {c['id']} is '{c['status']}' and cannot be merged")
    tag = gitops.snapshot(room)
    gitops.merge_branches(room, [c["branch"] for c in cs], f"Approved by {approver}")
    for c in cs:
        ex("UPDATE changes SET status='merged' WHERE id=?", (c["id"],))
    if any(c.get("kind") == "bootstrap" for c in cs):
        ex("UPDATE rooms SET bootstrapped=1 WHERE id=?", (room,))
    mid = ex(
        "INSERT INTO merges(room_id,change_ids,snapshot,approver,ts) VALUES(?,?,?,?,?)",
        (room, json.dumps(change_ids), tag, approver, now()),
    )
    for p in {
        m["part"]
        for m in q("SELECT part FROM memory WHERE room_id=? AND kind='failure'", (room,))
        if m["part"]
    }:
        memory.add(
            room,
            "failure",
            "platform",
            {"state": "ok", "cleared_by_merge": mid},
            part=p,
            by_platform=True,
        )
    return {"merge_id": mid, "snapshot": tag}


def undo(room, merge_id):
    m = q1("SELECT * FROM merges WHERE id=? AND room_id=? AND undone=0", (merge_id, room))
    if not m:
        raise ValueError("nothing to undo")
    gitops.undo_to(room, m["snapshot"])
    ex("UPDATE merges SET undone=1 WHERE id=?", (merge_id,))
    for i in json.loads(m["change_ids"]):
        ex("UPDATE changes SET status='undone' WHERE id=?", (i,))
        if (q1("SELECT kind FROM changes WHERE id=?", (i,)) or {}).get("kind") == "bootstrap":
            ex("UPDATE rooms SET bootstrapped=0 WHERE id=?", (room,))
    return {"restored": m["snapshot"]}
