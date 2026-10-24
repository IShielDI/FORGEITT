# TRD: ForgeIt Technical Requirements Document

Companion to PRD.md and ARCHITECTURE.md. Status: v2 (fixes applied).

## 1. Technology Choices

| Layer | Choice | Reason |
|-------|--------|--------|
| Frontend | Next.js (JavaScript) | Matches the code already built |
| Backend | FastAPI (Python 3.11+) | Async, WebSockets, good AI/tooling ecosystem |
| Database | SQLite (WAL mode, foreign keys on) | Zero setup, single file; Postgres is a later option |
| ORM | SQLAlchemy 2 | Standard, explicit models |
| Realtime | FastAPI WebSockets (single instance) | No extra infra |
| Jobs | In-process worker + DB-backed job table | No extra services |
| LLM access | One provider adapter shared by two paths (see section 6) | Single place for keys, budget and ledger |
| Providers | Claude first; then one OpenAI-compatible adapter (DeepSeek, OpenAI, Gemini); `mock` and Ollama for tests | Per-workspace allow-list |
| Agent harness | Wrapped CLI inside the sandbox, talking to the model proxy | Reuse, do not rebuild |
| Sandboxing | Docker: one container per task, one for the mirror, internal network | Isolation |
| Referee | TinyFish browser agent against the running candidate | Independent behavior check |
| Mail | Gmail SMTP | Invite delivery |
| Git | Managed repos with a protected main | Protected main without GitHub dependency |
| CI | GitHub Actions for the platform repo | Free minutes |
| Testing | pytest, the web app's own test runner, scripted e2e | |

## 2. Repository Layout
```
/
  apps/
    api/            FastAPI service
      app/
        core/       config, db, security
        models/     SQLAlchemy models
        schemas/    Pydantic schemas
        routers/    HTTP and WS endpoints
        services/   chat, spec, planner, knowledge, runner, proxy, verify, referee, router, merge, credits, invites
        llm/        provider adapter, prompts
        workers/    job runner
      tests/
    web/            Next.js app (JavaScript)
  sandbox/          Dockerfiles for agent and mirror images, proxy config
  samples/          demo target app
  docs/             PRD, TRD, ARCHITECTURE, adr/, source/
  scripts/
  .github/workflows/
  AGENTS.md  BUILD_PROMPTS.md  README.md
```

## 3. Data Model (core tables)

- `users(id, name, email)`
- `workspaces(id, name, slug, owner_id, verification_profile, allowed_providers, created_at)`; `slug` is a display name only, never a credential
- `members(workspace_id, user_id, role[owner|member|viewer], token_hash)`
- `invites(id, workspace_id, token_hash, role, created_by, expires_at, used_at, used_by)`; single-use, 7-day expiry
- `messages(id, workspace_id, user_id, body, created_at)`
- `spec_items(id, workspace_id, kind[requirement|decision|suggestion|question], text, status[proposed|confirmed|rejected], source_message_ids, version, created_by, confirmed_by)`
- `spec_versions(id, workspace_id, version, snapshot_json, created_at)`
- `contracts(id, workspace_id, kind[api|schema|type], name, content, version, status)`
- `tasks(id, workspace_id, title, description, owner_id, component, status, branch, depends_on, contract_ids)`
- `knowledge_links(id, workspace_id, src_type, src_id, dst_type, dst_id, relation, version)`
- `submissions(id, task_id, commit_sha, handoff_summary, status, created_at)`
- `integration_runs(id, workspace_id, candidate_branch, base_sha, status, profile, started_at, finished_at)`
- `check_results(id, run_id, name, kind, command, exit_code, duration_ms, status, log_path, artifacts_json)`
- `hidden_tests(id, workspace_id, author_id, approved_by, location, status)`; location is outside any agent-readable path
- `referee_runs(id, run_id, verdict, evidence_json, started_at, finished_at)`
- `failures(id, run_id, check_result_id, suspected_task_id, suspected_contract_id, confidence, evidence_json, status)`
- `approvals(id, run_id, approver_id, candidate_sha, decision, comment, merged_sha, created_at)`
- `credit_ledger(id, workspace_id, user_id, kind[portion|usage|loan|house], amount_usd, provider, model, task_id, created_at)`
- `jobs(id, type, payload, status, attempts, created_at)`

Rules: confirmed spec items and contracts are append-only; edits create a new version. A confirmed suggestion becomes a `decision` item.

Conventions (implemented in `apps/api/app/models`, Alembic migration `0001`, batch mode for SQLite):
- Every table has a string UUID `id` (`VARCHAR(36)`) plus `created_at` and `updated_at`.
- Every workspace-scoped table indexes `workspace_id`, with `ON DELETE CASCADE`.
- Enums are stored as lowercase values with named `CHECK` constraints, so the database rejects unknown values even outside the ORM.
- List fields (`source_message_ids`, `depends_on`, `contract_ids`, `allowed_providers`) and `*_json`/`payload` are JSON. `amount_usd` is `NUMERIC(12,6)`.
- Every connection sets `foreign_keys=ON`, `journal_mode=WAL` and a busy timeout. Relative SQLite paths resolve from the repo root.
- Check constraints: versions >= 1; failure `confidence` in [0, 1]; `merged_sha` only on an approved decision; invite `used_at` and `used_by` set together.
- `referee_runs.verdict` defaults to `not_run`, never `pass`. `hidden_tests` stores only the location, never test source. `check_results.command` and `duration_ms` record stage 16 evidence.
- Apply the schema with `cd apps/api && alembic upgrade head`.

## 4. API Surface (REST + WS)

- `POST /workspaces`, `GET /workspaces/{id}`
- `POST /workspaces/{id}/invites`, `POST /invites/{token}/accept` (no joining by room code)
- `GET/POST /workspaces/{id}/messages`; `WS /ws/workspaces/{id}`
- `GET /workspaces/{id}/spec`, `POST /spec/items/{id}/confirm|reject|edit`
- `POST /workspaces/{id}/plan/generate`, `POST /plan/approve`
- `GET/POST /workspaces/{id}/contracts`
- `GET /tasks/{id}/context`
- `POST /tasks/{id}/start`, `POST /tasks/{id}/submit`
- `POST /workspaces/{id}/integration-runs`, `GET /integration-runs/{id}`
- `GET /integration-runs/{id}/failures`, `POST /failures/{id}/resolve`
- `POST /integration-runs/{id}/approve|reject`
- `GET /workspaces/{id}/credits`, `POST /workspaces/{id}/credits/loans`
- Internal only (sandbox network): model proxy endpoint, authenticated by a per-task proxy token

## 5. Key Technical Requirements

**R1 Suggestion vs decision.** The observer returns structured JSON `{kind, text, source_message_ids, confidence}`. Only human-confirmed items become `confirmed`, and a confirmed suggestion becomes a `decision` item. Prompts and schemas are versioned in `llm/prompts`.

**R2 Context retrieval.** `GET /tasks/{id}/context` returns the task, its confirmed requirements, linked decisions, relevant contracts (pinned versions), dependency task summaries, and recent failures on the component. Output has a token budget and cites item IDs.

**R3 Isolation.**
- Each task gets its own full clone of the workspace repo, mounted read-write into its container. The sandbox never sees the protected repo, the protected mount, or a worktree linked to it.
- Containers run as non-root with CPU, memory and time limits and no host mounts other than the clone.
- Containers have no model keys. Their only network route is the platform model proxy on an internal Docker network (`internal: true`), because Docker has no native domain allowlist.
- The proxy holds the provider keys, checks the per-task token, enforces the budget, and writes the ledger.

**R4 Protected main.** Main lives in a repo whose only writer is the merge service. A server-side guard rejects pushes to main from agent branches. The approval row must exist for the exact candidate SHA before merge. Every merge is snapshotted and tagged so it can be undone.

**R5 Mirror build.** Create `candidate/<run_id>` from main, merge submitted task branches in dependency order, and run checks in a fresh container. Merge conflicts are a first-class failure type.

**R6 Verification and merge rule.**
- A human approves every merge, in every profile. Profiles change only how much verification runs before the human is asked.
- Verdicts derive only from command exit codes and artifacts, never from agent claims.
- Profiles:
  - `fast`: build, locked tests, hidden tests.
  - `standard`: fast + lint, contract conformance, dependency scan, secret scan, referee smoke journey.
  - `strict`: standard + full referee journeys; any non-`pass` referee verdict blocks approval.

**R7 Contract checks.** Validate the candidate against the pinned contract versions (OpenAPI/schema).

**R8 Failure routing.** Map a failing check to files via test names and stack traces, files to tasks via branch history and component ownership, then to contracts. Output ranked suspects with confidence and rationale. Never assert certainty. Low confidence goes to the workspace owner.

**R9 Traceability.** All entities carry creator, timestamps and versions. Knowledge links connect requirement, task, commit and check result.

**R10 Security.** No secrets in logs, prompts, sandboxes or the repo. Env-based config. Rate-limit LLM calls. Treat chat text, repo content and LLM output as untrusted input; validate with schemas.

**R11 Referee.** The referee drives the running candidate through user journeys using TinyFish and returns one verdict:
`pass`, `app_failure`, `browser_failure`, `service_error`, `inconclusive`, `not_run`.
- Only `pass` counts as a pass.
- `app_failure` routes through the failure router.
- `browser_failure` and `service_error` are infrastructure issues and are not attributed to a task.
- `inconclusive` and `not_run` are shown to the approver and never treated as a pass.
- Evidence (screenshots, traces, reproduction steps) is stored with the run.
- The integration is not yet tested against the real TinyFish API.

**R12 Locked and hidden tests.** Locked tests cannot be edited by agents. Hidden tests are written by a human after the first build, stored outside any agent-readable path, and mounted only in the mirror at verify time. Agents and the UI see pass/fail and failure messages, never the test source.

**R13 Credits ledger.**
- Each member gets a portion of the workspace budget.
- Checkpoints at 70%, 80% and 90% of a portion notify the member; 100% stops the proxy for that member.
- Optional loans let one member lend credit to another.
- Optional house key funds usage with a dollar cap per workspace and per person (caps pending team decision).
- Every model call, from either LLM path, records a `credit_ledger` row.

**R14 Invites and mail.** Invites are single-use links with 7-day expiry, delivered by Gmail SMTP, stored only as hashes. Accepting creates a per-member token. A room name or slug is never accepted as a credential.

## 6. LLM Requirements

Two paths share one provider adapter and one ledger:
1. **Platform LLMClient** (observer, planner, handoff, referee scripting): runs inside the backend, `complete(messages, schema=None)`.
2. **Sandbox harness**: the coding agent in a container, calling the platform model proxy, which uses the same adapter.

Common rules:
- Providers: Claude first, then the OpenAI-compatible adapter, plus `mock` and Ollama for tests; allowed providers are set per workspace.
- Prices and model IDs are looked up and tested before being relied on.
- Structured output validated with Pydantic; one retry on invalid JSON.
- Log prompt version and token counts, never keys.

## 7. Testing Strategy
- Unit tests per service; API tests per router.
- Integration tests with the mock LLM and temp git repos.
- E2E (finale demo loop): task, agent run, mirror, referee verdict, human approval, using mock providers in CI.
- Real-run test on the host before anything is called proven: Docker image, a Claude key, TinyFish, the tunnel.

## 8. Performance and Limits (MVP)
- Up to 6 concurrent members and 3 concurrent sandboxes. Docker Desktop needs at least 8 GB RAM on the host.

## 9. Deployment
- Local first: backend and web on the host laptop. Sandboxes, the mirror and the referee tunnel run on the same host with Docker.
- Provider keys (and any house key) live only in the backend environment on the host.

## 10. Definition of Done (per stage)
Code, tests, docs updated, CI green, one clean commit following AGENTS.md.
