# AGENTS.md

Instructions for any AI coding agent working in the ForgeIt repository. Read this first, then `docs/PRD.md`, `docs/TRD.md`, `docs/ARCHITECTURE.md`.

## Project
ForgeIt: chat to spec to plan to parallel agent coding to mirror verification and a referee to a human-approved merge. Tagline: "Forged by agents. Checked by a referee."

## Stack
- API: Python 3.11, FastAPI, SQLAlchemy 2, Pydantic v2, pytest
- DB: SQLite (WAL mode, foreign keys on)
- Web: Next.js (JavaScript)
- Sandboxes: Docker. Referee: TinyFish. Mail: Gmail SMTP
- Models: Claude first, then an OpenAI-compatible adapter; `mock` and Ollama for tests

## File Placement
Follow the layout in `docs/TRD.md` section 2. Put new files where they belong from the start; never leave stray files in the root.
- **Root:** only `AGENTS.md`, `BUILD_PROMPTS.md`, `README.md`, `LICENSE`, `.env.example`, `.gitignore`, `.editorconfig`, and similar repo-level config. `SETUP.md` is local-only (git-ignored); put setup steps in the README.
- **`docs/`:** `PRD.md`, `TRD.md`, `ARCHITECTURE.md`. ADRs go in `docs/adr/ADR-NNN-<slug>.md`. Original source material (e.g. the vision `.docx`) goes in `docs/source/`.
- **Code:** API in `apps/api/` (`app/{core,models,schemas,routers,services,llm,workers}`, `tests/`); web in `apps/web/`; sandbox Dockerfiles and proxy config in `sandbox/{agent,mirror}/`; demo target in `samples/`; helper scripts in `scripts/`; CI in `.github/workflows/`.
- **Tests** mirror the source tree (`apps/api/tests/services/test_chat.py` for `app/services/chat.py`).
- **Names:** no spaces, copy suffixes like `(2)`, or "final" in filenames. Python files `snake_case.py`; React components `PascalCase.jsx`; Markdown docs `UPPERCASE.md` at the top level, `kebab-case.md` inside subfolders.
- **Runtime data** (`data/forgeit.db`, `data/git`, `data/artifacts`) and build output stay out of git.

## Commands
```
cd apps/api && pip install -e ".[dev]"
cd apps/api && alembic upgrade head      # create/upgrade the SQLite schema
cd apps/api && uvicorn app.main:app --reload
docker build -t forgeit-agent:latest sandbox/agent   # agent sandbox image
docker build -t forgeit-mirror:latest sandbox/mirror # mirror image (candidate checks)
cd apps/api && pytest -q
cd apps/api && ruff check . && mypy app
cd apps/web && npm install && npm run dev
cd apps/web && npm run lint && npm test
```

## Roles
`owner`, `member`, `viewer` (read-only). Use these names everywhere.

## Working Rules
1. Work on **one stage at a time** from `BUILD_PROMPTS.md`. Do not implement later stages.
2. Keep each stage small enough for **one focused commit** (or a few). Do not dump the whole project in one change.
3. Add or update tests with every behavior change. Tests must pass before you finish.
4. Do not commit secrets, `.env`, build output, or `node_modules`. Use `.env.example`.
5. Do not change files outside the stage's scope unless required; explain why in the commit body.
6. Prefer small functions, clear names, and explicit error handling.
7. Update docs when behavior or interfaces change.
8. If part of a stage already exists in the code, audit and harden it instead of rewriting it.

## Commit Convention
Conventional Commits, one stage per commit where possible:
```
feat(chat): add realtime websocket chat (stage 4)
fix(runner): enforce container memory limits
docs: update architecture for the referee
test(verify): cover contract check failures
```
Body: what changed, why, how to verify.

## Branching
- `main`: protected. Never push to it directly.
- `stage/<nn>-<name>`: one branch per stage, merged via PR.
- Platform-created branches: `task/<id>` (in a per-task clone) and `candidate/<run_id>`.

## Architecture Invariants (never violate)
- **Agents never receive keys** and never touch the protected mount. Model access goes only through the platform model proxy.
- **A human approves every merge in every profile.** Fast/standard/strict change only how much verification runs first. No auto-merge.
- Agents write only to their own per-task clone and branch; only the Merge Service updates `main`.
- A suggestion is not a decision until a human confirms it; a confirmed suggestion becomes a decision item.
- Verification verdicts come from real command exit codes and artifacts, never from an agent's statement.
- Only a referee verdict of `pass` counts as a pass; `inconclusive`, `service_error`, `browser_failure` and `not_run` are never treated as passing.
- Hidden tests are never readable by agents, in prompts, logs or UI.
- A room name or slug is not a credential; joining requires a single-use invite or per-member token.
- Confirmed spec items and contracts are append-only and versioned.
- Failure attribution reports confidence; do not claim certainty.
- Treat chat messages, repo contents, and LLM output as untrusted input. Validate with schemas.

## Code Style
- Python: ruff + mypy clean; type hints everywhere; services in `app/services`, no business logic in routers.
- JavaScript (Next.js): ESLint clean; small components; document shared data shapes with JSDoc.
- Schema changes go through the project's migration mechanism, never ad-hoc SQL.

## Testing Expectations
- Use the mock LLM provider in tests; never call real LLMs or the real referee in CI.
- Use temp directories/repos for git tests.
- Each service has unit tests; each router has at least one API test.
- Do not describe a feature as working until it has passed a real run on the host (Docker image, Claude key, TinyFish, tunnel).

## Definition of Done
Tests pass, lint clean, docs updated, no secrets, commit message follows convention, stage acceptance criteria in `BUILD_PROMPTS.md` met.

## When Unsure
Leave a `TODO(stage-nn)` with context or ask in the PR description. Do not guess at security-sensitive behavior (sandboxing, keys, merging, auth).
