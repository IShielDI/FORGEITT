# Demo guide

## Offline (no keys)
```
bash scripts/demo.sh
```
Runs the scripted end-to-end test on `samples/todo-app` and the finale loop on the demo shop. It uses mock models, scripted agents and the offline referee stand-in. Every stand-in verdict is labelled; none of it is a TinyFish verdict.

## Recorded-demo checklist
Before recording:
- [ ] `docker build -t forgeit-agent:latest sandbox/agent` and `docker build -t forgeit-mirror:latest sandbox/mirror`
- [ ] Backend and web running (`uvicorn app.main:app`, `npm run build && npm start`); `pytest -q` green
- [ ] `.env` has a Claude key with a small budget (or members connect their own), `TINYFISH_API_KEY`, and a tunnel (`cloudflared` installed, or `PUBLIC_TUNNEL_URL`)
- [ ] Two browsers (or one private window) for two people

On camera:
1. Create a workspace from **Todo app**; copy the owner token; invite a teammate with a link (Setup tab).
2. Chat about a change in the **Chat** tab; press **Check the chat now** on **Spec**; confirm items (a suggestion becomes a decision).
3. **Plan** tab: propose a plan, assign owners, approve it (contracts pinned).
4. Each person presses **Start** on their task; watch **Runs** (activity feed, verdict ladder with every check and its exit code).
5. Show a failure routed to its owner with a confidence score, the fix, and the re-run.
6. Show the referee verdict and its evidence (video or screenshots) for a passing change.
7. The owner approves the merge (release tag), then undoes it to show rollback.

Say out loud what was **not** shown live: anything that used the offline stand-in or mock providers.
