# ForgeIt

*Forged by agents. Checked by a referee.*

**An AI-native collaborative coding workspace.** It turns team discussions into software, coordinates coding agents through shared project intelligence, and verifies their work before it reaches the main product.

## The Pitch
AI coding is fast, but team coding with AI is chaotic. Discussions happen in group chat, and each person's agent works from its own private context. Parallel agents assume different API shapes, they report "done" with no proof, and unverified code lands on main.

ForgeIt runs the whole team loop in one place:

1. **Discuss.** Create a workspace, invite teammates with single-use links, and chat as a team.
2. **Capture.** An observer agent turns the conversation into a living spec. A suggestion becomes a decision only after a human confirms it.
3. **Plan.** The platform proposes tasks, owners, dependencies, and shared contracts (API shapes, schemas, types) before anyone writes code.
4. **Build in parallel.** Each teammate's coding agent works in an isolated Docker sandbox on its own clone and branch, with a task-scoped context pack. Agents never hold model keys. They reach models only through the platform's model proxy, which enforces each member's credit budget.
5. **Verify independently.** Submitted work is combined in a mirror build and checked by real commands: build, locked tests, hidden tests (written by a human and never visible to agents), lint, and contract checks. The verdict comes from exit codes, not from what an agent claims.
6. **Referee.** A browser agent (TinyFish) drives the running candidate through user journeys. Only a `pass` verdict counts as a pass.
7. **Route failures.** Failures go to the likely owner with evidence and a confidence level, not blame.
8. **Merge with a human gate.** A human approves every merge, in every verification profile. Every merge is snapshotted and tagged so it can be undone.

```
Chat -> Observer -> Spec (human-confirmed) -> Planner -> Tasks + Contracts
     -> per-task clone + sandbox -> agent (via model proxy) -> Submit
     -> Mirror build -> Checks (locked + hidden tests) -> Referee verdict
     -> pass: human approval -> protected main (snapshot + tag)
     -> fail: Failure Router -> owner + evidence -> resubmit
```

## Stack
FastAPI (Python 3.11), SQLAlchemy 2, SQLite (WAL mode), Next.js (JavaScript), Docker sandboxes behind an internal network, TinyFish referee, Gmail SMTP for invites, and one provider adapter (Claude first, then OpenAI-compatible providers, plus `mock` and Ollama for tests).

## Repository Layout
```
apps/api/       FastAPI service (core, models, schemas, routers, services, llm, workers)
apps/web/       Next.js app (JavaScript)
sandbox/        Dockerfiles for agent and mirror images, proxy config
samples/        Demo target app
docs/           PRD, TRD, ARCHITECTURE, ADRs, source material
scripts/        Helper scripts
.github/        CI workflows
```

## Roadmap
The project is built one stage at a time. See [BUILD_PROMPTS.md](BUILD_PROMPTS.md) for each stage's prompt and acceptance criteria.

| # | Stage | # | Stage |
|---|-------|---|-------|
| 0 | Repo and docs | 13 | Sandboxes, per-task clones and model proxy |
| 1 | Backend skeleton + CI | 14 | Submission and handoff |
| 2 | Database and models | 15 | Mirror integration |
| 3 | Workspaces and invites | 16 | Verification engine, locked and hidden tests |
| 4 | Realtime chat | 17 | Referee and failure routing |
| 5 | Frontend shell | 18 | Human approval, merge and finale demo loop |
| 6 | LLM adapter and credits ledger | 19 | Verification profiles |
| 7 | Observer agent | 20 | Security checks |
| 8 | Spec editor and approval | 21 | Referee journeys from requirements |
| 9 | Planner and contracts | 22 | Hidden-test authoring workflow |
| 10 | Knowledge store | 23 | Demo app and e2e |
| 11 | Context retrieval | 24 | Polish and docs |
| 12 | Git service + protected main | 25 | House key and extra providers |

**Finale slice (MVP):** stages 0 to 18. **Later work:** stages 19 to 25.

## Getting Started
**Prerequisites:** Git 2.40+, Python 3.11, Node.js 20+, and Docker (Docker Desktop with at least 8 GB RAM; on Windows, use the WSL2 backend). For real runs you also need a Claude API key, a TinyFish API key, a tunnel tool, and a Gmail app password. None of these are needed for development: `LLM_PROVIDER=mock` works without keys.

Copy `.env.example` to `.env` (never commit `.env`). Keys live only in the backend environment and never enter a sandbox. Then:
```
cd apps/api && python -m venv .venv && .venv/Scripts/activate   # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head                     # creates data/forgeit.db (SQLite)
uvicorn app.main:app --reload            # http://localhost:8000/docs

cd apps/web && npm install && npm run dev   # http://localhost:3000
```
The SQLite database lives at `data/forgeit.db` in the repo root, whichever folder you run from. These commands become available as their stages land (backend from stage 1, web from stage 5). Contributors and AI agents should read [AGENTS.md](AGENTS.md) first.

## Documentation
- [Product Requirements (PRD)](docs/PRD.md)
- [Technical Requirements (TRD)](docs/TRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Product vision (source)](docs/source/product-vision.docx)

## License
[MIT](LICENSE)
