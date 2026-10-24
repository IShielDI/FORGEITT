"""Architecture graph: owners, dependencies, build order, affected parts, and the live system map."""

import json

from app.core.db import ex, q, q1
from app.services.gitops import original


def seed_parts(room, members_by_name):
    mp = json.loads((original(room) / "protected/contracts/map.json").read_text())
    for name, p in mp["parts"].items():
        ex(
            "INSERT INTO parts(room_id,name,owner,paths,depends_on) VALUES(?,?,?,?,?)",
            (room, name, p["owner"], json.dumps(p["paths"]), json.dumps(p["depends_on"])),
        )
    return mp


def parts(room):
    return [
        {**p, "paths": json.loads(p["paths"]), "depends_on": json.loads(p["depends_on"])}
        for p in q("SELECT * FROM parts WHERE room_id=?", (room,))
    ]


def build_order(room):
    """Layers by dependency: parts in the same layer don't depend on each other and can build at once."""
    ps = {p["name"]: set(p["depends_on"]) for p in parts(room)}
    layers, done = [], set()
    while ps:
        ready = sorted(n for n, d in ps.items() if d <= done)
        if not ready:
            raise ValueError("dependency cycle")
        layers.append(ready)
        done |= set(ready)
        for n in ready:
            del ps[n]
    return layers


def owner_of(room, part):
    p = q1("SELECT owner FROM parts WHERE room_id=? AND name=?", (room, part))
    return p["owner"] if p else None


def part_for_path(room, path):
    best = None
    for p in parts(room):
        for pat in p["paths"]:
            if path.split("#")[0] == pat.split("#")[0] or path.startswith(pat.split("#")[0]):
                best = best or p["name"]
    return best


def affected_by(room, part):
    """The part plus everything that depends on it (what to re-test after it changes)."""
    out, changed = {part}, True
    ps = parts(room)
    while changed:
        changed = False
        for p in ps:
            if p["name"] not in out and set(p["depends_on"]) & out:
                out.add(p["name"])
                changed = True
    return sorted(out)


def system_map(room):
    mp = json.loads((original(room) / "protected/contracts/map.json").read_text())
    covered = set(mp["test_to_part"].values())
    failing = {}
    for m in q(
        "SELECT part, content FROM memory WHERE room_id=? AND kind='failure' ORDER BY id", (room,)
    ):
        failing[m["part"]] = json.loads(m["content"]).get("state", "failing")
    nodes = []
    for p in parts(room):
        nodes.append(
            {
                "name": p["name"],
                "owner": p["owner"],
                "depends_on": p["depends_on"],
                "tested": p["name"] in covered or p["name"] == "qa",
                "state": failing.get(p["name"], "ok"),
            }
        )
    return {"nodes": nodes, "build_order": build_order(room), "journeys": mp["journeys"]}
