# BUILD_PROMPTS.md (ForgeIt)

Stage-by-stage build prompts. Each stage is one branch and one (or a few) commits so the GitHub history shows the project growing step by step.

**Finale slice = stages 0 to 18.** Stages 19 onward are later work.

**Stack:** FastAPI, SQLite, Next.js (JavaScript). Much of the finale slice already exists in code (workspaces and invites, protected main and human-approved merge, Docker runner, mirror, locked and hidden tests, referee, credits ledger). For a stage that already exists, audit and harden it against the acceptance criteria instead of rewriting it. Not yet built: chat, spec, planner, knowledge retrieval, profiles, security scans.

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
| 3 | Workspaces and invites | `feat(workspace): create workspaces and join by single-use invite` |
| 4 | Realtime chat | `feat(chat): add message history and websocket chat` |
| 5 | Frontend shell | `feat(web): add Next.js shell with create/join and chat UI` |
| 6 | LLM adapter and credits ledger | `feat(llm): add provider adapter, mock and credits ledger` |
| 7 | Observer agent | `feat(spec): extract suggestions and decisions from chat` |
| 8 | Spec editor and approval | `feat(spec): versioned spec with confirm/reject/edit` |
| 9 | Planner and contracts | `feat(plan): generate tasks, owners, dependencies and contracts` |
| 10 | Knowledge store | `feat(knowledge): versioned links across requirements, tasks, results` |
| 11 | Context retrieval | `feat(context): task-scoped context packs` |
| 12 | Git service + protected main | `feat(git): managed repos with protected main and task branches` |
| 13 | Sandboxes, per-task clones and model proxy | `feat(runner): isolated per-task containers behind a model proxy` |
| 14 | Submission and handoff | `feat(submit): task submission with handoff summary` |
| 15 | Mirror integration | `feat(integration): build candidate branch from task branches` |
| 16 | Verification engine, locked and hidden tests | `feat(verify): run checks, locked and hidden tests with evidence` |
| 17 | Referee and failure routing | `feat(referee): TinyFish verdicts and failure attribution` |
| 18 | Human approval, merge and finale demo loop | `feat(merge): approval-gated merge, undo and finale demo loop` |
| 19 | Verification profiles | `feat(verify): fast, standard and strict profiles` |
| 20 | Security checks | `feat(verify): dependency and secret scanning` |
| 21 | Referee journeys from requirements | `feat(referee): journeys drafted from approved requirements` |
| 22 | Hidden-test authoring workflow | `feat(verify): human authoring and approval of hidden tests` |
| 23 | Demo app and e2e | `test(e2e): sample app end-to-end demo flow` |
| 24 | Polish and docs | `docs: finalize README, ADRs and demo guide` |
| 25 | House key and extra providers | `feat(llm): capped house key and OpenAI-compatible providers` |

Stages 0 to 18 are the finale slice (MVP). 19 to 25 are later work.

---

## Stage 0: Repo and Docs
**Goal:** Repository with documentation and conventions.
**Prompt:**
> Create the repo layout from TRD section 2 with empty folders kept via `.gitkeep`. Add `docs/` with PRD, TRD, ARCHITECTURE, root AGENTS.md, BUILD_PROMPTS.md, a `.gitignore` (Python, Node, env, data/), `.editorconfig`, MIT `LICENSE`, and a README with the project pitch and stage roadmap.
**Verify:** `git status` clean; README renders.
**Acceptance:** Docs present, structure matches TRD.

## Stage 1: Backend Skeleton and CI
**Prompt:**
> In `apps/api`, create a FastAPI app with `pyproject.toml` (deps: fastapi, uvicorn, sqlalchemy, pydantic-settings; dev: pytest, httpx, ruff, mypy). Add `app/main.py`, `app/core/config.py` (settings from env), `GET /health`. Add `.env.example` (no real values) and `.github/workflows/ci.yml` running ruff, mypy, pytest for api. SQLite needs no separate service.
**Verify:** `pytest -q`, `ruff check .`, `uvicorn` serves `/health`.
**Acceptance:** CI green on PR; `/health` returns `{"status":"ok"}`.

## Stage 2: Database and Models
**Prompt:**
> Add SQLAlchemy 2 base and session handling on SQLite (WAL mode, foreign keys on) with a migration mechanism that works on SQLite. Create models for: users, workspaces, members, invites, messages, spec_items, spec_versions, contracts, tasks, knowledge_links, submissions, integration_runs, check_results, hidden_tests, referee_runs, failures, approvals, credit_ledger, jobs (see TRD section 3). Use string UUID primary keys, timestamps, and enums. Add model tests against a temporary database file.
**Verify:** migrations apply to a fresh database and to the current schema; tests pass.
**Acceptance:** All tables exist with constraints and indexes on workspace_id.

## Stage 3: Workspaces and Invites
**Prompt:**
> Implement `POST /workspaces` (with a display name or slug that is never a credential), `GET /workspaces/{id}`, member listing, `POST /workspaces/{id}/invites` and `POST /invites/{token}/accept`. Invites are single-use, expire after 7 days, and are stored only as hashes; accepting issues a per-member token. Send the invite link by Gmail SMTP, with the link also shown to the owner as a fallback. Roles: owner, member, viewer. Put logic in `services/workspace.py` and `services/invites.py`.
**Verify:** API tests cover create, accept with valid, used, expired and unknown tokens, role assignment, access control. Mail sending is tested with a stub and confirmed later in the real-run test.
**Acceptance:** Non-members cannot read a workspace.

## Stage 4: Realtime Chat
**Prompt:**
> Add `GET/POST /workspaces/{id}/messages` and a WebSocket `/ws/workspaces/{id}` that authenticates the token, broadcasts new messages to room members, and persists them. Add a connection manager. Support message pagination.
**Verify:** Tests with two WebSocket clients receiving each other's messages; non-members rejected.
**Acceptance:** Messages persist and fan out in order.

## Stage 5: Frontend Shell
**Prompt:**
> In `apps/web`, scaffold Next.js (JavaScript). Pages: landing with create workspace and accept invite, and `/w/[id]` with a chat panel (history plus live WebSocket), member list, and placeholder panels for Spec, Plan, Runs. Add an API client module and env config. Keep the UI clean and responsive.
**Verify:** `npm run lint && npm test && npm run build`; manual two-browser chat test.
**Acceptance:** Two users can chat live from the browser.

## Stage 6: LLM Adapter and Credits Ledger
**Prompt:**
> Create `app/llm` with one provider adapter and a platform `LLMClient` interface `complete(messages, schema=None)`. Providers: Claude first, then one OpenAI-compatible adapter (base URL and key from env; covers DeepSeek, OpenAI, Gemini), Ollama, and a deterministic `mock` for tests. Allowed providers are set per workspace. Add Pydantic-validated structured output with one retry on invalid JSON and a prompt registry with versioned prompt files. Add `services/credits.py`: per-member portions of a workspace budget, a `credit_ledger` row for every model call, notifications at 70%, 80% and 90% of a portion, and a hard stop at 100%. Look up and test prices and model IDs before relying on them.
**Verify:** Unit tests with the mock; adapter tests with mocked HTTP; ledger tests for checkpoints and the hard stop.
**Acceptance:** Swapping `LLM_PROVIDER` requires no code change; every call is in the ledger. The sandbox harness reuses this adapter and ledger through the proxy in stage 13.

## Stage 7: Observer Agent
**Prompt:**
> Implement `services/observer.py`. On new messages (batched), call the LLM with the recent window and current spec to return structured items `{kind: requirement|decision|suggestion|question, text, source_message_ids, confidence}`. Store as `spec_items` with status `proposed`. Deduplicate against existing items. Never mark anything `confirmed`. Run it via the job worker so chat is not blocked. Treat chat text as untrusted; use schema validation.
**Verify:** Tests with mock LLM fixtures: a suggestion stays a suggestion; an explicit agreement yields a decision proposal.
**Acceptance:** Chat produces proposed spec items linked to source messages.

## Stage 8: Spec Editor and Approval
**Prompt:**
> Add spec endpoints: list, edit, confirm, reject. Confirm records the user, turns a confirmed suggestion into a `decision` item, and creates a new `spec_versions` snapshot; confirmed items are append-only (edits create a new version). Add a spec panel in the UI with badges for suggestion/decision/requirement, source message links, and confirm/reject buttons, updating live.
**Verify:** API tests for versioning and append-only rule; UI test for confirm flow.
**Acceptance:** Only confirmed items appear in the approved spec snapshot.

## Stage 9: Planner and Contracts
**Prompt:**
> Implement `services/planner.py`: from the confirmed spec, LLM proposes tasks (title, description, component, dependencies, suggested owner) and contracts (API shapes, DB schema, shared types). Store as proposed. Validate the dependency graph is acyclic. Endpoints to edit assignments, approve the plan, and version contracts. UI plan board with owner assignment and a dependency view. Contracts must be approved before tasks can start.
**Verify:** Tests for cycle detection, approval gating, contract versioning.
**Acceptance:** Approved plan with pinned contract versions.

## Stage 10: Knowledge Store
**Prompt:**
> Implement `services/knowledge.py` over `knowledge_links` with relations: requirement-task, decision-contract, contract-task, task-task, submission-commit, check_result-failure. Add helpers to create links automatically when plans are approved, and a traversal function with depth limit. All links versioned and traceable to creator and time.
**Verify:** Unit tests for link creation and traversal.
**Acceptance:** From any task you can trace back to requirements and decisions.

## Stage 11: Context Retrieval
**Prompt:**
> Implement `GET /tasks/{id}/context`. Build a context pack: task, linked confirmed requirements and decisions, pinned contract versions, dependency summaries, recent failures on the component. Enforce a token budget with priority-based trimming and include item IDs as citations. Return markdown plus JSON.
**Verify:** Tests ensure unrelated items are excluded and the budget is respected.
**Acceptance:** Two tasks get different, relevant contexts.

## Stage 12: Git Service and Protected Main
**Prompt:**
> Implement `services/git.py` using subprocess git on a managed repo per workspace under `GIT_STORAGE_PATH`: init with a seed commit, create `task/<id>` branches in per-task full clones (never a bare worktree linked to the protected repo), create candidate branches, merge in order, and tag releases. Add a server-side pre-receive style guard so only the merge service may update `main`. Never shell out with unsanitized input.
**Verify:** Tests with temp repos: branch creation, merge conflict detection, refused direct main write.
**Acceptance:** Main can only change through the merge service function.

## Stage 13: Sandboxes, Per-Task Clones and Model Proxy
**Prompt:**
> Add `sandbox/agent/Dockerfile` (non-root, git, Python, Node, chosen coding harness). Build the image at this stage. Implement `services/runner.py`: `POST /tasks/{id}/start` makes a full clone for the task on branch `task/<id>`, writes the context pack into it as `TASK_CONTEXT.md`, and starts a container with only that clone mounted, CPU/memory/time limits, and no keys. Implement `services/proxy.py`, a platform-side model proxy that holds the provider keys, checks a per-task token, enforces the budget, and writes the ledger through the shared provider adapter. Put the task containers on an internal Docker network (`internal: true`) whose only reachable service is the proxy, because Docker has no native domain allowlist. Stream logs to the UI. Support stop and timeout. Add a `mock` runner for tests and CI.
**Verify:** Integration test with mock runner; manual real-container run showing the container cannot reach the internet or see any key, and that a model call through the proxy appears in the ledger.
**Acceptance:** Agent edits only its own clone and branch; never receives a key or touches the protected mount; limits and budget enforced.

## Stage 14: Submission and Handoff
**Prompt:**
> Implement `POST /tasks/{id}/submit`: capture the head commit SHA, run a lightweight local check, generate a handoff summary (what changed, assumptions, contract deviations, how to test) via the LLM from the diff, and store a submission. Show submissions in the UI.
**Verify:** Tests for SHA capture and summary storage with the mock LLM.
**Acceptance:** Each task has a traceable submission linked to a commit.

## Stage 15: Mirror Integration
**Prompt:**
> Implement `services/integration.py`: create `candidate/<run_id>` from main, merge submitted task branches in dependency order, record conflicts as failures, and prepare a fresh build container from `sandbox/mirror/Dockerfile`. Build the mirror image at this stage (not earlier). Run the candidate app in that container on the `mirror` Docker network and expose it through the tunnel so the referee (stage 17) can reach it. Create an `integration_runs` row with status transitions. UI shows run status.
**Verify:** Tests with two non-conflicting branches and one conflicting pair; manual run showing the candidate app reachable through the tunnel.
**Acceptance:** Candidate branches rebuild from scratch in a fresh container; main untouched.

## Stage 16: Verification Engine
**Prompt:**
> Implement `services/verify.py` with a check registry. Checks: build, locked tests (agents cannot edit them), hidden tests, lint, contract conformance (OpenAPI/schema versus pinned contracts). Hidden tests are written by a human after the first build, stored outside any agent-readable path, and mounted only in the mirror at verify time; agents and the UI see pass/fail and messages, never the source. Each check runs in the mirror container and stores command, exit code, duration, log artifact, and status. The verdict is computed only from exit codes and artifacts. UI shows check results with logs.
**Verify:** Tests with a sample repo having passing and failing checks.
**Acceptance:** Verdict never depends on agent statements.

## Stage 17: Referee and Failure Routing
**Prompt:**
> Implement `services/router.py`: parse failing test names and stack traces to files, map files to task branches and component owners, check contract violations, and write `failures` rows with ranked suspects, confidence, rationale, and evidence. Notify the top suspect's owner in the UI with expected behavior, logs, and reproduction command. Low confidence goes to the workspace owner. Allow reassigning a failure.
>
> Add `services/referee.py`: expose the running candidate through the tunnel, have TinyFish drive a user journey, and store a `referee_runs` row with one verdict: `pass`, `app_failure`, `browser_failure`, `service_error`, `inconclusive`, `not_run`, plus screenshots, traces and reproduction steps. Only `pass` counts as a pass. `app_failure` goes to the router; `browser_failure` and `service_error` are infrastructure issues and are not attributed to a task; `inconclusive` and `not_run` are shown to the approver and never treated as passing.
**Verify:** Tests with seeded failures attributed to the correct task and an ambiguous case with low confidence.
**Acceptance:** Owner receives evidence-backed failure; attribution is never presented as certain. Referee verdicts are stored and shown; non-pass verdicts are never displayed as a pass. The real TinyFish API is exercised in the real-run test (not CI).

## Stage 18: Human Approval and Merge
**Prompt:**
> Implement `POST /integration-runs/{id}/approve|reject`. A human owner must approve every merge in every profile (no auto-merge). Approval requires that the run's required checks passed, shows the referee verdict, and is bound to the exact candidate SHA. The merge service fast-forwards or merges into main, tags `release/<n>`, and records `approvals`. Add rollback to a previous tag. UI approval panel showing diff, check evidence, and the approve/reject buttons. Optional push to a GitHub remote.
**Verify:** Tests: cannot merge without approval; cannot merge a stale SHA; rollback restores a previous tag.
Add `scripts/finale-demo`, one scripted path: task, agent run (through the model proxy), mirror build, referee verdict, human approval, merge, undo.
**Acceptance:** Finale slice complete: unverified changes cannot reach main, and the finale demo loop runs end to end on the host.

---

## Extension Stages

## Stage 19: Verification Profiles
> Add `fast`, `standard`, `strict` verification profiles as config mapping to check sets. `fast`: build, locked tests, hidden tests. `standard`: fast + lint, contract conformance, dependency scan, secret scan, referee smoke journey. `strict`: standard + full referee journeys, and any non-`pass` referee verdict blocks approval. A human approves every merge in every profile; profiles only change how much verification runs first, and nothing may enable auto-merge. Workspace setting plus UI selector. Tests per profile, including a test that no profile can merge without a recorded human approval.

## Stage 20: Security Checks
> Add dependency vulnerability scan (pip-audit / npm audit) and secret scan (gitleaks or a simple pattern scanner) as checks in standard and strict only (not fast), as defined in Stage 19. Fail on high severity or any detected secret.

## Stage 21: Referee Journeys from Requirements
> Extend the referee (built in stage 17) with journeys drafted from approved requirements. The LLM may draft journeys, a human reviews them before use. Collect screenshots, traces and reproduction steps as evidence; `app_failure` verdicts route through the router.

## Stage 22: Hidden-Test Authoring Workflow
> Add the human workflow for hidden tests (the mechanism itself is built in stage 16): a named teammate writes them after the first build, a second person approves them, and they are stored outside agent-readable paths. Results show pass/fail without revealing test source to agents. Document the threat model.

## Stage 23: Demo App and E2E
> Create `samples/todo-app` seed repo and a scripted e2e test: create workspace, simulate chat, confirm spec, approve plan, run two mock agents (one with a planted bug), integrate, observe routed failure, fix, re-run, approve merge. Add a `scripts/demo.sh` and a recorded-demo checklist.

## Stage 24: Polish and Docs
> Final README with architecture diagram, quickstart, and demo GIF; write ADR-001 to ADR-006; add CONTRIBUTING.md; tidy UI; ensure CI covers api, web, and e2e (mock mode).

## Stage 25: House Key and Extra Providers
> Add an optional house key for the credits ledger with a dollar cap per workspace and per person (caps set by the team), including optional loans between members. Add the OpenAI-compatible provider group (DeepSeek, OpenAI, Gemini) with prices and model IDs looked up and tested, selectable per workspace. The house key stays in the backend environment on the host and never enters a sandbox.

---

## Commit Hygiene Tips
- One stage, one branch, one PR; squash only if a stage has noisy WIP commits.
- If a stage is large, split into 2 to 3 commits: `feat` (code), `test`, `docs`.
- Tag milestones: `v0.1-chat` after stage 5, `v0.2-spec` after 8, `v0.3-plan` after 11, `v0.4-agents` after 14, `v0.5-verify` after 17, `v1.0-finale` after 18 (the finale slice).
