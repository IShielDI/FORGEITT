"""Finale demo loop (stage 18): one scripted path through the whole product.

    task -> agent run (sandbox, keys stay on the host) -> mirror build and checks
         -> referee verdict -> human approval -> merge (release tag) -> undo

Offline (default): a scripted agent and the labelled offline referee stand-in. Nothing here is a
TinyFish verdict, and the output says so.
Live: `python scripts/finale_demo.py --live` with ANTHROPIC_API_KEY (and optionally TINYFISH_API_KEY,
PUBLIC_TUNNEL_URL) uses a real Claude agent and, when configured, the real referee. Spend is capped
by BUDGET (dollars, default 2).
"""

import argparse
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", help="use a real Claude agent (needs ANTHROPIC_API_KEY)")
    ap.add_argument("--task", default="Tidy the cart page", help="the task given to the agent")
    args = ap.parse_args()
    if args.live and not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("--live needs ANTHROPIC_API_KEY")

    # an isolated, throwaway platform: never touches your real data
    os.environ.setdefault("PLATFORM_DATA", tempfile.mkdtemp(prefix="forgeit-demo-data-"))
    state = os.environ.setdefault("PLATFORM_STATE", tempfile.mkdtemp(prefix="forgeit-demo-state-"))
    os.environ["DATABASE_URL"] = f"sqlite:///{Path(state, 'forgeit.db').as_posix()}"
    os.environ["REQUIRE_AUTH"] = "0"
    os.environ.setdefault("VERIFICATION_PROFILE", "standard")
    if not args.live:
        os.environ["REFEREE_STANDIN"] = "1"
        os.environ["ALLOW_UNSAFE_SANDBOX"] = "1"  # scripted agent: no model-written commands run
    sys.path.insert(0, str(ROOT / "apps" / "api"))

    from fastapi.testclient import TestClient

    from app.core.db import q1
    from app.main import app
    from app.services import agent_runner, orchestrator

    c = TestClient(app)
    budget = float(os.environ.get("BUDGET", "2"))
    key = os.environ.get("ANTHROPIC_API_KEY") if args.live else None
    members = [{"name": "riya", "contribution": budget, **({"anthropic_key": key} if key else {})}, {"name": "aman"}]
    rid = c.post("/api/rooms", json={"name": "finale", "members": members}).json()["id"]
    print(f"1. workspace {rid} created (demo shop, locked + hidden tests)")

    provider = None
    if not args.live:
        from app.core.db import ex
        from tests.support import scenarios

        ex("INSERT OR IGNORE INTO prices VALUES('scripted', 0, 0, 0, 0)")  # the scripted agent is free
        provider = scenarios.SCENARIOS["fix_ui"]()
    run = agent_runner.run_task(rid, "riya-agent", args.task, provider=provider, summary=args.task)
    print(f"2. agent run: {run['status']} in {run['steps']} steps ({'real Claude' if args.live else 'scripted agent'})")
    if not run["change_id"]:
        print("   no change produced: stopping here")
        return 1
    ch = orchestrator.submit_change(rid, run["change_id"])
    print(f"3. mirror build and checks: {ch['status']}")
    res = orchestrator.run_referee(rid, force=True) or {}
    ch = q1("SELECT * FROM changes WHERE id=?", (run["change_id"],))
    runner = "offline stand-in (NOT a TinyFish verdict)" if not args.live else "TinyFish"
    print(f"4. referee verdict: {res.get('verdict', 'not run')} via {runner}; change is now {ch['status']}")
    if ch["status"] != "passed":
        print("   not approvable: a human would read the evidence and route the fix")
        return 0
    merged = orchestrator.approve(rid, [ch["id"]], "riya (human)")
    print(f"5. human approval -> merged {merged['merged_sha'][:10]} tagged {merged['release']}")
    undone = orchestrator.undo(rid, merged["merge_id"])
    print(f"6. undo -> main restored to {undone['restored']}")
    print(f"data in {os.environ['PLATFORM_DATA']} (throwaway)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
