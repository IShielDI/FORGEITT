# Contributing to ForgeIt

Read [AGENTS.md](AGENTS.md) first: it holds the working rules, file placement, architecture invariants and the definition of done. The product and technical docs are in [docs/](docs/).

## Workflow
1. One stage or change at a time, on a branch `stage/<nn>-<name>` (or `fix/<name>`). `main` is protected.
2. Add or update tests with every behaviour change. Use the mock LLM provider and temp repos; never call real models or the real referee in tests.
3. Before opening a pull request:
   ```
   cd apps/api && ruff check . && ruff format --check . && mypy app && pytest -q
   cd apps/web && npm run lint && npm test && npm run build
   ```
4. Schema changes go through an Alembic migration (`alembic revision --autogenerate`), never ad-hoc SQL.
5. Commit with Conventional Commits (`feat(spec): ...`, `fix(runner): ...`), and say what changed, why and how to verify it.

## Things that are never acceptable
- Keys or secrets in code, logs, prompts, sandboxes, or `.env` committed.
- Any path that merges to `main` without a recorded human approval of the verified commit.
- Treating a referee verdict other than `pass` as passing, or claiming certainty in failure attribution.
- Showing hidden test source to agents, in prompts, logs or the UI.

## Real runs
Do not describe a feature as working until it has passed a real run on the host: Docker images built, a Claude key, TinyFish, and the tunnel. See [docs/DEMO.md](docs/DEMO.md).
