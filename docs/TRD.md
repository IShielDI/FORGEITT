# TRD: Technical Requirements Document

Companion to PRD.md and ARCHITECTURE.md.

## 1. Technology Choices

| Layer | Choice | Reason |
|-------|--------|--------|
| Frontend | Next.js (TypeScript), Tailwind | Fast to build, free hosting on Vercel |
| Backend | FastAPI (Python 3.11+) | Async, WebSockets, good AI/tooling ecosystem |
| Database | PostgreSQL 16 (local Docker; Supabase/Neon free tier hosted) | Relational plus JSONB; versioned records |
| ORM/Migrations | SQLAlchemy 2 + Alembic | Standard, explicit migrations |
| Realtime | FastAPI WebSockets (single instance) | No extra infra |
| Queue/Jobs | In-process worker + DB-backed job table (upgrade to Redis/RQ later) | Zero extra services |
| LLM access | Provider-agnostic adapter (Gemini, Groq, OpenRouter, Ollama) | Free-tier flexibility |
| Agent harness | Wrapped CLI (Aider first; OpenHands/opencode optional) | Reuse, do not rebuild |
| Sandboxing | Docker (one container per task, one for mirror) | Isolation, free |
| Git | Local bare repos managed by the backend; optional GitHub sync | Protected main without GitHub dependency |
| CI | GitHub Actions for the platform repo itself | Free minutes |
| Browser tests | Playwright | Open source |
| Testing | pytest, Vitest, Playwright | |

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
        services/   chat, spec, planner, knowledge, runner, verify, router, merge
        llm/        provider adapters, prompts
        workers/    job runner
      tests/
      alembic/
    web/            Next.js app
  sandbox/          Dockerfiles for agent and mirror images
  samples/          demo target app
  docs/             PRD, TRD, ARCHITECTURE, ADRs
  scripts/
  .github/workflows/
  AGENTS.md  BUILD_PROMPTS.md  README.md  docker-compose.yml
```

## 3. Data Model (core tables)

- `users(id, name, email)`
- `workspaces(id, room_code, name, owner_id, verification_profile, created_at)`
- `members(workspace_id, user_id, role)`
- `messages(id, workspace_id, user_id, body, created_at)`
- `spec_items(id, workspace_id, kind[requirement|decision|suggestion|question], text, status[proposed|confirmed|rejected], source_message_ids[], version, created_by, confirmed_by)`
- `spec_versions(id, workspace_id, version, snapshot_json, created_at)`
- `contracts(id, workspace_id, kind[api|schema|type], name, content, version, status)`
- `tasks(id, workspace_id, title, description, owner_id, component, status, branch, depends_on[], contract_ids[])`
- `knowledge_links(id, workspace_id, src_type, src_id, dst_type, dst_id, relation, version)`
- `submissions(id, task_id, commit_sha, handoff_summary, status, created_at)`
- `integration_runs(id, workspace_id, candidate_branch, base_sha, status, profile, started_at, finished_at)`
- `check_results(id, run_id, name, kind, command, exit_code, duration_ms, status, log_path, artifacts_json)`
- `failures(id, run_id, check_result_id, suspected_task_id, suspected_contract_id, confidence, evidence_json, status)`
- `approvals(id, run_id, approver_id, decision, candidate_sha, comment, merged_sha, created_at)`
- `jobs(id, type, payload, status, attempts, created_at)`

Rule: confirmed spec items and contracts are append-only. Edits create a new version.

Conventions (implemented in `apps/api/app/models`, migration `0001`): every table has a UUID `id` (`gen_random_uuid()`), `created_at` and `updated_at`; every workspace-scoped table indexes `workspace_id` with `ON DELETE CASCADE`; status and kind fields are native Postgres enums; `[]` fields are `uuid[]` and `*_json`/`payload` are `jsonb`. `check_results.command`/`duration_ms` record evidence per R6, and `approvals.candidate_sha` binds an approval to the exact candidate SHA (ARCHITECTURE section 4). Check constraints: versions >= 1, failure `confidence` in [0, 1], and `merged_sha` only on an approved decision.

## 4. API Surface (REST + WS)

- `POST /workspaces`, `POST /workspaces/join` (room code), `GET /workspaces/{id}`
- `GET/POST /workspaces/{id}/messages`; `WS /ws/workspaces/{id}`
- `GET /workspaces/{id}/spec`, `POST /spec/items/{id}/confirm|reject|edit`
- `POST /workspaces/{id}/plan/generate`, `POST /plan/approve`
- `GET/POST /workspaces/{id}/contracts`
- `GET /tasks/{id}/context` (retrieved context pack)
- `POST /tasks/{id}/start` (create branch and sandbox), `POST /tasks/{id}/submit`
- `POST /workspaces/{id}/integration-runs`, `GET /integration-runs/{id}`
- `GET /integration-runs/{id}/failures`, `POST /failures/{id}/resolve`
- `POST /integration-runs/{id}/approve|reject`

## 5. Key Technical Requirements

**R1 Suggestion vs decision.** The observer returns structured JSON `{kind, text, source_message_ids, confidence}`. Only human-confirmed items become `confirmed`. Prompts and schemas are versioned in `llm/prompts`.

**R2 Context retrieval.** `GET /tasks/{id}/context` returns: the task, its confirmed requirements, linked decisions, relevant contracts (pinned versions), dependency task summaries, and recent failures on the component. Output has a token budget and cites item IDs.

**R3 Isolation.** Per-task container: non-root user, no host mounts except the task worktree, CPU/memory/time limits, no secrets, restricted network (LLM endpoint allowlist only). Agents get a worktree on branch `task/<id>`.

**R4 Protected main.** Main lives in a repo whose only writer is the merge service. Server-side hook rejects pushes to main from agent branches. Approvals are recorded before merge. Every merge is tagged for rollback.

**R5 Mirror build.** Create `candidate/<run_id>` from main, merge submitted task branches in dependency order, run checks in a fresh container. Merge conflicts are a first-class failure type.

**R6 Verification.** Each check records command, exit code, duration, and log artifact. Verdict derives only from these. Profiles: `light` (build, unit tests), `standard` (+lint, contract checks, dependency scan), `strict` (+secret scan, browser journeys, hidden tests, human review required).

**R7 Contract checks.** Validate OpenAPI/schema conformance of the candidate against the pinned contract versions.

**R8 Failure routing.** Map a failing check to files via stack traces/test names, map files to tasks via git blame on branches plus component ownership, then to contracts. Output ranked suspects with a confidence and rationale. Never assert certainty.

**R9 Traceability.** All entities carry created_by, timestamps, and versions. Knowledge links connect requirement to task to commit to check result.

**R10 Security.** No secrets in logs or prompts; env-based config; basic auth/session; rate limit LLM calls; sanitize any text that is rendered or put into prompts (treat chat and repo content as untrusted input to agents).

## 6. LLM Requirements
- Single `LLMClient` interface: `complete(messages, schema=None)`.
- Structured output validated with Pydantic; one retry on invalid JSON.
- Provider and model chosen by env; mock provider for tests.
- Logging of prompt version and token counts, not raw secrets.

## 7. Testing Strategy
- Unit tests per service; contract tests for API schemas.
- Integration tests using the mock LLM and a temp git repo.
- E2E test: the sample app flows through plan, two tasks, one planted failure, fix, and merge.

## 8. Performance and Limits (MVP)
- Up to 6 concurrent members, 3 concurrent sandboxes, chat latency under 500 ms locally.

## 9. Deployment
- Local: `docker compose up`.
- Hosted demo (optional): web on Vercel, api on Render/Fly, Postgres on Neon/Supabase. Sandboxes require Docker access, so keep them on a local machine or VM for the demo.

## 10. Definition of Done (per stage)
Code, tests, docs updated, CI green, one clean commit following the convention in AGENTS.md.
