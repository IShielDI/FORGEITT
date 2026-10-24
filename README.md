# FORGEITT

**An AI-native collaborative coding workspace.** It turns team discussions into software, coordinates coding agents through shared project intelligence, and verifies their work before it reaches the main product.

## The Pitch
AI coding is fast, but team coding with AI is chaotic. Discussions happen in group chat, and each person's agent works from its own private context. Parallel agents assume different API shapes, they report "done" with no proof, and unverified code lands on main.

FORGEITT runs the whole team loop in one place:

1. **Discuss.** Create a room, share the code, and chat as a team.
2. **Capture.** An observer agent turns the conversation into a living spec. A suggestion becomes a decision only after a human confirms it.
3. **Plan.** The platform proposes tasks, owners, dependencies, and shared contracts (API shapes, schemas, types) before anyone writes code.
4. **Build in parallel.** Each teammate's coding agent works in an isolated sandbox on its own branch, with a task-scoped context pack drawn from versioned project knowledge.
5. **Verify independently.** Submitted work is combined in a mirror build and checked by real commands: build, tests, lint, contract checks, security scans, and browser journeys. The verdict comes from exit codes, not from what an agent claims.
6. **Route failures.** Failures go to the likely owner with evidence and a confidence level, not blame.
7. **Merge with a human gate.** Only a human approval lets the Merge Service write to the protected `main`. Every merge is tagged so it can be rolled back.

```
Chat -> Observer -> Spec (human-confirmed) -> Planner -> Tasks + Contracts
     -> per-task sandbox + agent -> Submit -> Mirror build -> Checks
     -> pass: human approval -> protected main (tagged)
     -> fail: Failure Router -> owner + evidence -> resubmit
```

## Stack
FastAPI (Python 3.11), SQLAlchemy 2, Alembic, PostgreSQL 16, Next.js (TypeScript) with Tailwind, Docker sandboxes, Playwright, and a provider-agnostic LLM client (Gemini, Groq, OpenRouter, Ollama, or a mock).

## Repository Layout
```
apps/api/       FastAPI service (core, models, schemas, routers, services, llm, workers)
apps/web/       Next.js app
sandbox/        Dockerfiles for agent and mirror images
samples/        Demo target app
docs/           PRD, TRD, ARCHITECTURE, ADRs, source material
scripts/        Helper scripts
.github/        CI workflows
```

## Roadmap
The project is built one stage at a time. See [BUILD_PROMPTS.md](BUILD_PROMPTS.md) for each stage's prompt and acceptance criteria.

| # | Stage | # | Stage |
|---|-------|---|-------|
| 0 | Repo and docs | 13 | Sandboxes and agent runner |
| 1 | Backend skeleton + CI | 14 | Submission and handoff |
| 2 | Database and models | 15 | Mirror integration |
| 3 | Workspaces and members | 16 | Verification engine |
| 4 | Realtime chat | 17 | Failure routing |
| 5 | Frontend shell | 18 | Human approval and merge |
| 6 | LLM adapter | 19 | Adaptive profiles |
| 7 | Observer agent | 20 | Security checks |
| 8 | Spec editor and approval | 21 | Browser testing agent |
| 9 | Planner and contracts | 22 | Hidden tests |
| 10 | Knowledge store | 23 | Demo app and e2e |
| 11 | Context retrieval | 24 | Polish and docs |
| 12 | Git service + protected main | | |

**MVP:** stages 0 to 18. **Extensions:** stages 19 to 24.

## Getting Started
**Prerequisites:** Git 2.40+, Python 3.11, Node.js 20+, and Docker (on Windows, Docker Desktop with the WSL2 backend). An LLM API key (Gemini, Groq, or OpenRouter) or a local Ollama is optional, because `LLM_PROVIDER=mock` works without a key.

Copy `.env.example` to `.env` (never commit `.env`). Then:
```
docker compose up -d db
cd apps/api && python -m venv .venv && .venv/Scripts/activate   # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn app.main:app --reload            # http://localhost:8000/docs

cd apps/web && npm install && npm run dev   # http://localhost:3000
```
These commands become available as their stages land (backend from stage 1, database from stage 2, web from stage 5). Contributors and AI agents should read [AGENTS.md](AGENTS.md) first.

## Documentation
- [Product Requirements (PRD)](docs/PRD.md)
- [Technical Requirements (TRD)](docs/TRD.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Product vision (source)](docs/source/product-vision.docx)

## License
[MIT](LICENSE)
