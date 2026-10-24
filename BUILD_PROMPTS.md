# BUILD_PROMPTS.md

Stage-by-stage build prompts. Each stage is one branch and one (or a few) commits so the GitHub history shows the project growing step by step.

## How to Use
For each stage:
1. `git switch -c stage/NN-name`
2. Open your coding agent and say: *"Read AGENTS.md and docs/PRD.md, TRD.md, ARCHITECTURE.md. Implement ONLY the stage below. Do not implement other stages."*
3. Paste the stage prompt.
4. Run the checks in **Verify**. Fix until green.
5. Commit with the **Commit** message, push, open a PR, merge.

Global constraints for every prompt: follow AGENTS.md, add tests, keep scope to the stage, no secrets committed.

## Stage Map

| # | Stage | Commit message |
|---|-------|----------------|
| 0 | Repo and docs | `docs: add PRD, TRD, architecture, agents and build plan` |
| 1 | Backend skeleton + CI | `feat(api): bootstrap FastAPI service with health check and CI` |
| 2 | Database and models | `feat(db): add core schema and migrations` |
| 3 | Workspaces and members | `feat(workspace): create and join workspaces by room code` |
| 4 | Realtime chat | `feat(chat): add message history and websocket chat` |
| 5 | Frontend shell | `feat(web): add Next.js shell with create/join and chat UI` |
| 6 | LLM adapter | `feat(llm): add provider-agnostic client with mock` |
| 7 | Observer agent | `feat(spec): extract suggestions and decisions from chat` |
| 8 | Spec editor and approval | `feat(spec): versioned spec with confirm/reject/edit` |
| 9 | Planner and contracts | `feat(plan): generate tasks, owners, dependencies and contracts` |
| 10 | Knowledge store | `feat(knowledge): versioned links across requirements, tasks, results` |
| 11 | Context retrieval | `feat(context): task-scoped context packs` |
| 12 | Git service + protected main | `feat(git): managed repos with protected main and task branches` |
| 13 | Sandboxes and agent runner | `feat(runner): isolated per-task agent containers` |
| 14 | Submission and handoff | `feat(submit): task submission with handoff summary` |
| 15 | Mirror integration | `feat(integration): build candidate branch from task branches` |
| 16 | Verification engine | `feat(verify): run checks and record evidence` |
| 17 | Failure routing | `feat(router): attribute failures to tasks and contracts` |
| 18 | Human approval and merge | `feat(merge): approval-gated merge with tags and rollback` |
| 19 | Adaptive profiles | `feat(verify): light, standard and strict profiles` |
| 20 | Security checks | `feat(verify): dependency and secret scanning` |
| 21 | Browser testing agent | `feat(browser): Playwright journey testing` |
| 22 | Hidden tests | `feat(verify): protected tests hidden from agents` |
| 23 | Demo app and e2e | `test(e2e): sample app end-to-end demo flow` |
| 24 | Polish and docs | `docs: finalize README, ADRs and demo guide` |

Stages 0 to 18 are the MVP. 19 to 24 are extensions.

---

## Stage 0: Repo and Docs
**Goal:** Repository with documentation and conventions.
**Prompt:**
> Create the repo layout from TRD section 2 with empty folders kept via `.gitkeep`. Add `docs/` with PRD, TRD, ARCHITECTURE, root AGENTS.md, BUILD_PROMPTS.md, a `.gitignore` (Python, Node, env, data/), `.editorconfig`, MIT `LICENSE`, and a README with the project pitch and stage roadmap.
**Verify:** `git status` clean; README renders.
**Acceptance:** Docs present, structure matches TRD.

## Stage 1: Backend Skeleton and CI
**Prompt:**
> In `apps/api`, create a FastAPI app with `pyproject.toml` (deps: fastapi, uvicorn, sqlalchemy, alembic, psycopg, pydantic-settings; dev: pytest, httpx, ruff, mypy). Add `app/main.py`, `app/core/config.py` (settings from env), `GET /health`. Add `docker-compose.yml` with Postgres 16, `.env.example`, and `.github/workflows/ci.yml` running ruff, mypy, pytest for api.
**Verify:** `pytest -q`, `ruff check .`, `uvicorn` serves `/health`.
**Acceptance:** CI green on PR; `/health` returns `{"status":"ok"}`.

---

<!-- TODO(stage-02): append the full prompts for Stages 2 to 24 here (Goal / Prompt / Verify / Acceptance), in the same format as above. -->
