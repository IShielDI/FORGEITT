"""LIVE run: real Claude agents, no scripted plans.
Usage:  ANTHROPIC_API_KEY=sk-ant-... python scripts/live_demo.py "<task for backend agent>" "<task for frontend agent>"
Tasks are YOUR words (not written by the platform). Optional env: TINYFISH_API_KEY, MIRROR_PUBLIC_URL, AGENT_SANDBOX=docker,
MODEL (default from config), BUDGET (dollars of this key you allow, default 2).
Nothing here asserts what the agents will do: it prints what actually happened. Cost is capped by BUDGET."""
import os, sys, tempfile
if len(sys.argv) < 3 or not os.environ.get("ANTHROPIC_API_KEY"):
    sys.exit(__doc__)
os.environ.setdefault("PLATFORM_DATA", tempfile.mkdtemp(prefix="forgeit-live-"))
os.environ["REQUIRE_AUTH"] = "0"   # in-process run: no web logins needed
# Real model commands need isolation: build the Docker image (docker build -t forgeit-agent:latest sandbox/agent) or, on a throwaway machine, set ALLOW_UNSAFE_SANDBOX=1.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))
from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app, raise_server_exceptions=True)
budget = float(os.environ.get("BUDGET", "2"))
key = os.environ["ANTHROPIC_API_KEY"]
rid = c.post("/api/rooms", json={"name": "live", "members": [
    {"name": n, "anthropic_key": key, "contribution": round(budget / 3, 2)} for n in ("riya", "aman", "kriti")]}).json()["id"]
# solo test: the same key is registered for all three members so each agent has a portion (budget/3 each)
ids = {m["name"]: m["id"] for m in c.get(f"/api/rooms/{rid}").json()["members"]}
print("agents:", [(a["name"], a["part"]) for a in c.get(f"/api/rooms/{rid}").json()["agents"]])

def run(agent, task):
    print(f"\n=== {agent}: {task}")
    r = c.post(f"/api/rooms/{rid}/agents/{agent}/run", json={"task": task}).json()   # no scenario => real model
    print("result:", {k: v for k, v in r.items() if k != "change"})
    ch = r.get("change")
    if ch: print("change status:", ch["status"], "| steps:", ch.get("steps"))
    return r

run("aman-agent", sys.argv[1])
run("riya-agent", sys.argv[2])
print("\nblocked attempts:", [(a["action"], a["path"]) for a in c.get(f"/api/rooms/{rid}/attempts").json()])
print("contract-change requests:", len(c.get(f"/api/rooms/{rid}/memory", params={"kind": "contract-change"}).json()))
res = c.post(f"/api/rooms/{rid}/referee/run").json(); print("\nreferee:", res)
for ch in c.get(f"/api/rooms/{rid}/changes").json():
    d = c.get(f"/api/changes/{ch['id']}").json()
    rf = (d.get("evidence") or {}).get("referee") or {}
    print(f"change {ch['id']} [{d['status']}] runner={rf.get('runner')} verdict={rf.get('verdict')} {rf.get('reason', '')}")
print("budget:", c.get(f"/api/rooms/{rid}/budget", params={"member": ids['riya']}).json())
print("DATA:", os.environ["PLATFORM_DATA"], "(approve through the UI/API; the merge stays human)")
