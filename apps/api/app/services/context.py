"""Task-scoped context packs (stage 11, TRD R2).

A pack holds: the task, its confirmed requirements and decisions, the pinned contract versions,
summaries of the tasks it depends on, and recent failures on its component. Items are added by
priority until the token budget is used; every item carries a citation id. Unrelated items are
never included.
"""

import json
from typing import Any

from app.core.db import q, q1
from app.services import knowledge, planner

DEFAULT_BUDGET = 2000
CHARS_PER_TOKEN = 4  # rough estimate; good enough for trimming


def tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


def _candidates(t: dict[str, Any]) -> list[dict[str, Any]]:
    rid = t["room_id"]
    out: list[dict[str, Any]] = []
    for f in knowledge.relevant_files(rid, t["id"]):
        out.append(
            {
                "cite": f"file:{f['path']}",
                "priority": 0,
                "section": "Relevant files (start here; other files are probably unrelated)",
                "text": f"{f['path']} ({f['why']})",
            }
        )
    for cid in t["contract_ids"]:
        c = q1("SELECT * FROM contracts WHERE id=?", (cid,))
        if c:
            out.append(
                {
                    "cite": f"contract:{c['id']}",
                    "priority": 1,
                    "section": "Contracts (pinned)",
                    "text": f"{c['name']} v{c['version']} ({c['kind']}): {c['content']}",
                }
            )
    trace = knowledge.trace_task(rid, t["id"])
    for kind in ("requirement", "decision"):
        for sid in trace[kind]:
            s = q1("SELECT * FROM spec_items WHERE id=? AND status='confirmed'", (sid,))
            if s:
                out.append(
                    {
                        "cite": f"spec:{s['id']}",
                        "priority": 2,
                        "section": "Requirements and decisions",
                        "text": f"[{s['kind']}] {s['text']}",
                    }
                )
    by_key = {r["key"]: r for r in q("SELECT * FROM tasks WHERE room_id=?", (rid,))}
    for dep in t["depends_on"]:
        d = by_key.get(dep)
        if d:
            out.append(
                {
                    "cite": f"task:{d['id']}",
                    "priority": 3,
                    "section": "Tasks this depends on",
                    "text": f"{d['title']} ({d['status']}): {(d['description'] or '')[:300]}",
                }
            )
    if t["component"]:
        for f in q(
            "SELECT * FROM memory WHERE room_id=? AND kind='failure' AND part=? ORDER BY id DESC LIMIT 3",
            (rid, t["component"]),
        ):
            body = json.loads(f["content"] or "{}")
            if body.get("state", "failing") == "failing":
                out.append(
                    {
                        "cite": f"failure:{f['id']}",
                        "priority": 4,
                        "section": "Recent failures on this component",
                        "text": str(body.get("why") or body.get("reason") or "failure")[:300],
                    }
                )
    return out


def build(task_id: int, budget: int = DEFAULT_BUDGET) -> dict[str, Any]:
    t = planner.task(task_id)
    head = f"# Task {t['key']}: {t['title']} [task:{t['id']}]\n\n{t['description'] or ''}\n"
    used, included, trimmed = tokens(head), [], []
    for item in sorted(_candidates(t), key=lambda i: i["priority"]):
        cost = tokens(item["text"]) + 4
        if used + cost > budget:
            trimmed.append(item["cite"])
            continue
        used += cost
        included.append(item)
    md = [head]
    for section in dict.fromkeys(i["section"] for i in included):
        md.append(f"\n## {section}\n")
        md += [f"- {i['text']} [{i['cite']}]" for i in included if i["section"] == section]
    return {
        "task_id": t["id"],
        "markdown": "\n".join(md).strip() + "\n",
        "items": [
            {"cite": i["cite"], "section": i["section"], "text": i["text"]} for i in included
        ],
        "tokens": used,
        "budget": budget,
        "trimmed": trimmed,
    }
