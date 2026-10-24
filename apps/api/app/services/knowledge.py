"""Knowledge store (stage 10): typed, versioned links between project entities (ARCHITECTURE §8).

Relations: requirement/decision -> task (implemented_by), decision -> contract (specifies),
contract -> task (constrains), task -> task (depends_on), change -> commit (produced),
check -> failure (raised), failure -> task (suspects). Every link records who made it and when.
"""

import json
from collections import deque
from typing import Any

from app.core.db import ex, now, q, q1

SPEC_TYPES = ("requirement", "decision", "suggestion", "question")
MAX_DEPTH = 6


def link(
    room_id: int,
    src_type: str,
    src_id: Any,
    dst_type: str,
    dst_id: Any,
    relation: str,
    created_by: int | None = None,
) -> int:
    """Create a link (idempotent: an identical existing link is returned instead)."""
    existing = q1(
        "SELECT id FROM knowledge_links WHERE room_id=? AND src_type=? AND src_id=? AND dst_type=? "
        "AND dst_id=? AND relation=?",
        (room_id, src_type, str(src_id), dst_type, str(dst_id), relation),
    )
    if existing:
        return int(existing["id"])
    return ex(
        "INSERT INTO knowledge_links(room_id,src_type,src_id,dst_type,dst_id,relation,created_by,created) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (room_id, src_type, str(src_id), dst_type, str(dst_id), relation, created_by, now()),
    )


def links(room_id: int) -> list[dict[str, Any]]:
    return q("SELECT * FROM knowledge_links WHERE room_id=? ORDER BY id", (room_id,))


def traverse(
    room_id: int,
    node_type: str,
    node_id: Any,
    direction: str = "back",
    depth: int = 3,
    skip: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    """Breadth-first walk from a node. `back` follows links into the node (what it came from);
    `forward` follows links out of it. Returns the visited links, nearest first."""
    if direction not in ("back", "forward"):
        raise ValueError("direction must be 'back' or 'forward'")
    depth = max(0, min(depth, MAX_DEPTH))
    seen_nodes = {(node_type, str(node_id))}
    found: list[dict[str, Any]] = []
    frontier: deque[tuple[str, str, int]] = deque([(node_type, str(node_id), 0)])
    while frontier:
        t, i, d = frontier.popleft()
        if d >= depth:
            continue
        if direction == "back":
            rows = q(
                "SELECT * FROM knowledge_links WHERE room_id=? AND dst_type=? AND dst_id=?",
                (room_id, t, i),
            )
            nxt = [(r, r["src_type"], r["src_id"]) for r in rows]
        else:
            rows = q(
                "SELECT * FROM knowledge_links WHERE room_id=? AND src_type=? AND src_id=?",
                (room_id, t, i),
            )
            nxt = [(r, r["dst_type"], r["dst_id"]) for r in rows]
        for row, nt, ni in nxt:
            if row["relation"] in skip:
                continue
            found.append({**row, "depth": d + 1})
            if (nt, ni) not in seen_nodes:
                seen_nodes.add((nt, ni))
                frontier.append((nt, ni, d + 1))
    return found


def trace_task(room_id: int, task_id: int, depth: int = 3) -> dict[str, list[int]]:
    """From a task back to what is behind it: the requirements it implements, the contracts it is
    pinned to, and the decisions behind it (directly or through those contracts). Dependencies and
    other tasks' requirements are deliberately not followed."""
    del depth  # kept for API compatibility; the walk below is exactly two hops
    into_task = traverse(room_id, "task", task_id, "back", depth=1)
    out: dict[str, set[int]] = {"requirement": set(), "decision": set(), "contract": set()}
    for row in into_task:
        if row["relation"] == "implemented_by" and row["src_type"] in ("requirement", "decision"):
            out[row["src_type"]].add(int(row["src_id"]))
        elif row["relation"] == "constrains" and row["src_type"] == "contract":
            out["contract"].add(int(row["src_id"]))
    for cid in list(out["contract"]):
        for row in traverse(room_id, "contract", cid, "back", depth=1):
            if row["relation"] == "specifies" and row["src_type"] == "decision":
                out["decision"].add(int(row["src_id"]))
    return {k: sorted(v) for k, v in out.items()}


def _spec_kind(item_id: int) -> str | None:
    row = q1("SELECT kind FROM spec_items WHERE id=?", (item_id,))
    return row["kind"] if row and row["kind"] in SPEC_TYPES else None


def link_plan(room_id: int, created_by: int | None = None) -> int:
    """Called when a plan is approved: link spec items, contracts and tasks. Returns links made."""
    made = 0
    by_key = {t["key"]: t["id"] for t in q("SELECT id, key FROM tasks WHERE room_id=?", (room_id,))}
    for t in q("SELECT * FROM tasks WHERE room_id=? AND status!='proposed'", (room_id,)):
        for sid in json.loads(t["spec_item_ids"] or "[]"):
            kind = _spec_kind(sid)
            if kind:
                link(room_id, kind, sid, "task", t["id"], "implemented_by", created_by)
                made += 1
        for cid in json.loads(t["contract_ids"] or "[]"):
            link(room_id, "contract", cid, "task", t["id"], "constrains", created_by)
            made += 1
        for dep in json.loads(t["depends_on"] or "[]"):
            if dep in by_key:
                link(room_id, "task", by_key[dep], "task", t["id"], "depends_on", created_by)
                made += 1
    for c in q("SELECT * FROM contracts WHERE room_id=? AND status='approved'", (room_id,)):
        for sid in json.loads(c["spec_item_ids"] or "[]"):
            kind = _spec_kind(sid)
            if kind:
                link(room_id, kind, sid, "contract", c["id"], "specifies", created_by)
                made += 1
    return made


# ---------------------------------------------------------------------------
# Files in the graph: what an agent should look at for a task, and the project map view
# ---------------------------------------------------------------------------
def _part_files(room_id: int, part: str) -> list[str]:
    row = q1("SELECT paths FROM parts WHERE room_id=? AND name=?", (room_id, part))
    if not row:
        return []
    return sorted({p.split("#")[0] for p in json.loads(row["paths"] or "[]") if p})


def link_change_files(room_id: int, change_id: int, files: list[str]) -> int:
    """Record which files a change touched (change -> file), so later tasks can find them."""
    for f in files:
        link(room_id, "change", change_id, "file", f, "touched")
    return len(files)


def relevant_files(room_id: int, task_id: int) -> list[dict[str, str]]:
    """Files to start from for a task, each with the reason it is relevant:
    the task's own part, files its dependencies changed, and files linked to recent failures."""
    task = q1("SELECT * FROM tasks WHERE id=?", (task_id,))
    if not task:
        raise LookupError("no such task")
    out: dict[str, str] = {}
    component = task["component"] or ""
    for f in _part_files(room_id, component):
        out.setdefault(f, f"part '{component}'")
    by_key = {t["key"]: t["id"] for t in q("SELECT id, key FROM tasks WHERE room_id=?", (room_id,))}
    for dep in json.loads(task["depends_on"] or "[]"):
        if dep not in by_key:
            continue
        for row in traverse(room_id, "task", by_key[dep], "forward", depth=2):
            if row["dst_type"] == "file":
                out.setdefault(row["dst_id"], f"changed by dependency '{dep}'")
    for f in q(
        "SELECT content FROM memory WHERE room_id=? AND kind='failure' AND part=? ORDER BY id DESC LIMIT 3",
        (room_id, component),
    ):
        body = json.loads(f["content"] or "{}")
        if body.get("state", "failing") == "failing":
            for path in body.get("files") or []:
                out.setdefault(path.split("#")[0], "linked to a recent failure")
    for row in traverse(room_id, "task", task_id, "forward", depth=2):
        if row["dst_type"] == "file":
            out.setdefault(row["dst_id"], "changed by an earlier run of this task")
    return [{"path": p, "why": why} for p, why in sorted(out.items())]


def in_scope(path: str, allowed: list[str]) -> bool:
    """A path is in scope if it equals an allowed file or sits under an allowed folder."""
    p = path.lstrip("./")
    return any(p == a or (a.endswith("/") and p.startswith(a)) for a in allowed)


def project_graph(room_id: int) -> dict[str, Any]:
    """Nodes and edges for the map view: spec items, contracts, tasks, parts, files, changes,
    commits and open failures, joined by the knowledge links and the part map."""
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, str]] = []

    def node(nid: str, ntype: str, label: str, status: str = "") -> str:
        nodes.setdefault(nid, {"id": nid, "type": ntype, "label": label[:80], "status": status})
        return nid

    def edge(a: str, b: str, relation: str) -> None:
        edges.append({"source": a, "target": b, "relation": relation})

    for s in q(
        "SELECT id, kind, text, status FROM spec_items WHERE room_id=? AND status IN ('proposed','confirmed')",
        (room_id,),
    ):
        node(f"{s['kind']}:{s['id']}", s["kind"], s["text"], s["status"])
    for c in q(
        "SELECT id, name, version, status FROM contracts WHERE room_id=? AND status!='superseded'",
        (room_id,),
    ):
        node(f"contract:{c['id']}", "contract", f"{c['name']} v{c['version']}", c["status"])
    for t in q("SELECT id, key, title, status, component FROM tasks WHERE room_id=?", (room_id,)):
        tid = node(f"task:{t['id']}", "task", t["title"], t["status"])
        if t["component"] and q1(
            "SELECT 1 x FROM parts WHERE room_id=? AND name=?", (room_id, t["component"])
        ):
            edge(tid, node(f"part:{t['component']}", "part", t["component"]), "works_on")
    for p in q("SELECT name, owner, depends_on FROM parts WHERE room_id=?", (room_id,)):
        pid = node(f"part:{p['name']}", "part", p["name"], p["owner"] or "")
        for f in _part_files(room_id, p["name"]):
            edge(pid, node(f"file:{f}", "file", f), "owns")
        for d in json.loads(p["depends_on"] or "[]"):
            edge(pid, node(f"part:{d}", "part", d), "depends_on")
    for ch in q("SELECT id, summary, status FROM changes WHERE room_id=?", (room_id,)):
        node(f"change:{ch['id']}", "change", ch["summary"] or f"change {ch['id']}", ch["status"])
    for f in q(
        "SELECT id, part, content FROM memory WHERE room_id=? AND kind='failure'", (room_id,)
    ):
        body = json.loads(f["content"] or "{}")
        if body.get("state") != "failing":
            continue
        fid = node(f"failure:{f['id']}", "failure", body.get("why") or "failure", "failing")
        if f["part"]:
            edge(fid, node(f"part:{f['part']}", "part", f["part"]), "suspects")
    for lk in links(room_id):
        a = f"{lk['src_type']}:{lk['src_id']}"
        b = f"{lk['dst_type']}:{lk['dst_id']}"
        label_a = lk["src_id"] if lk["src_type"] in ("file", "commit") else a
        label_b = (
            lk["dst_id"][:10]
            if lk["dst_type"] == "commit"
            else (lk["dst_id"] if lk["dst_type"] == "file" else b)
        )
        node(a, lk["src_type"], label_a)
        node(b, lk["dst_type"], label_b)
        edge(a, b, lk["relation"])
    return {"nodes": list(nodes.values()), "edges": edges}
