# AGENTS.md

Instructions for any AI coding agent working in this repository. Read this first, then `docs/PRD.md`, `docs/TRD.md`, `docs/ARCHITECTURE.md`.

## Project
AI-Native Collaborative Coding Workspace: chat to spec to plan to parallel agent coding to mirror verification to human-approved merge.

## Stack
- API: Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, pytest
- Web: Next.js (TypeScript), Tailwind, Vitest
- DB: PostgreSQL 16 via Docker Compose
- Sandboxes: Docker. Browser tests: Playwright

## File Placement
Follow the layout in `docs/TRD.md` section 2. Put new files where they belong from the start; never leave stray files in the root.
- **Root:** only `AGENTS.md`, `SETUP.md`, `BUILD_PROMPTS.md`, `README.md`, `docker-compose.yml`, `.env.example`, `.gitignore`, and similar repo-level config.
- **`docs/`:** `PRD.md`, `TRD.md`, `ARCHITECTURE.md`. ADRs go in `docs/adr/ADR-NNN-<slug>.md`. Original source material (e.g. the vision `.docx`) goes in `docs/source/`.
- **Code:** API in `apps/api/` (`app/{core,models,schemas,routers,services,llm,workers}`, `tests/`, `alembic/`); web in `apps/web/`; sandbox Dockerfiles in `sandbox/{agent,mirror}/`; demo target in `samples/`; helper scripts in `scripts/`; CI in `.github/workflows/`.
- **Tests** mirror the source tree (`apps/api/tests/services/test_chat.py` for `app/services/chat.py`).
- **Names:** no spaces, copy suffixes like `(2)`, or "final" in filenames. Python files `snake_case.py`; React components `PascalCase.tsx`; Markdown docs `UPPERCASE.md` at the top level, `kebab-case.md` inside subfolders.
- **Runtime data** (`data/git`, `data/artifacts`) and build output stay out of git.

## Commands
```
docker compose up -d db          # start Postgres
cd apps/api && pip install -e ".[dev]"
cd apps/api && alembic upgrade head
cd apps/api && uvicorn app.main:app --reload
cd apps/api && pytest -q
cd apps/api && ruff check . && mypy app
cd apps/web && npm install && npm run dev
cd apps/web && npm run lint && npm test
```

## Working Rules
1. Work on **one stage at a time** from `BUILD_PROMPTS.md`. Do not implement later stages.
2. Keep each stage small enough for **one focused commit** (or a few). Do not dump the whole project in one change.
3. Add or update tests with every behavior change. Tests must pass before you finish.
4. Do not commit secrets, `.env`, build output, or `node_modules`. Use `.env.example`.
5. Do not change files outside the stage's scope unless required; explain why in the commit body.
6. Prefer small functions, typed signatures, and explicit error handling.
7. Update docs when behavior or interfaces change.

## Commit Convention
Conventional Commits, one stage per commit where possible:
```
feat(chat): add realtime websocket chat (stage 4)
fix(runner): enforce container memory limits
docs: update architecture for failure router
test(verify): cover contract check failures
```
Body: what changed, why, how to verify.

## Branching
- `main`: protected. Never push to it directly.
- `stage/<nn>-<name>`: one branch per stage, merged via PR.
- Agent task branches created by the platform: `task/<id>`. Candidate branches: `candidate/<run_id>`.

## Architecture Invariants (never violate)
- Agents never write to `main`. Only the Merge Service merges, and only after a recorded human approval.
- A suggestion is not a decision until a human confirms it.
- Verification verdicts come from real command exit codes and artifacts, never from an agent's statement.
- Confirmed spec items and contracts are append-only and versioned.
- Failure attribution reports confidence; do not claim certainty.
- Treat chat messages, repo contents, and LLM output as untrusted input. Validate with schemas.
- No secrets inside sandboxes or prompts.

## Code Style
- Python: ruff + mypy clean; type hints everywhere; services in `app/services`, no business logic in routers.
- TypeScript: strict mode; no `any` without a comment; components small and typed.
- SQL changes only through Alembic migrations.

## Testing Expectations
- Use the mock LLM provider in tests; never call real LLMs in CI.
- Use temp directories/repos for git tests.
- Each service has unit tests; each router has at least one API test.

## Definition of Done
Tests pass, lint and types clean, docs updated, no secrets, commit message follows convention, stage acceptance criteria in `BUILD_PROMPTS.md` met.

## When Unsure
Ask in the PR description or leave a `TODO(stage-nn)` with context. Do not guess at security-sensitive behavior (sandboxing, merging, auth).
