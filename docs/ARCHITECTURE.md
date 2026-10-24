# ForgeIt Architecture

*Forged by agents. Checked by a referee.*

## 1. System Overview

```
 Browser (Next.js)
   | HTTP + WebSocket
   v
 FastAPI Backend ------------------------------------------+
   |-- Chat Service                                         |
   |-- Observer (LLM) --> Spec Service                      |
   |-- Planner (LLM)  --> Task/Contract Service             |
   |-- Knowledge Store + Context Retriever                  |
   |-- Invites + Mail (Gmail SMTP)                          |
   |-- Credits Ledger  <------------------+                 |
   |-- Provider Adapter (shared) ---------+--> Model APIs   |
   |        ^                 ^                             |
   |  Platform LLMClient   Model Proxy (holds keys, budget) |
   |-- Agent Runner ---> Docker sandboxes ---(internal net)-+--> Model Proxy
   |-- Integration Service --> Mirror build                 |
   |-- Verification Engine (checks, locked + hidden tests)  |
   |-- Referee (TinyFish) --> running candidate             |
   |-- Failure Router                                       |
   |-- Merge Service (human gate)                           |
   v                                                        |
 SQLite                                                     |
 Git storage: main (protected), per-task clones, candidate/*|
 Artifact store (logs, screenshots)  <----------------------+
```

## 2. Components

| Component | Responsibility |
|-----------|----------------|
| Chat Service | Workspaces, membership, message persistence, realtime fan-out |
| Invites + Mail | Single-use invite links (7-day expiry), per-member tokens, Gmail SMTP |
| Observer | Reads new messages, emits structured proposals (suggestion/decision/requirement/question) |
| Spec Service | Versioned spec; confirm/reject/edit; a confirmed suggestion becomes a decision item |
| Planner | Proposes tasks, owners, dependencies, components, contracts |
| Contract Registry | Versioned API/schema/type contracts agents must follow |
| Knowledge Store | Typed, versioned links across requirement, decision, contract, task, commit, check result |
| Context Retriever | Builds a task-scoped, budgeted context pack with citations |
| Provider Adapter | One adapter for Claude, OpenAI-compatible providers, mock and Ollama |
| Model Proxy | Platform-side; holds provider keys, checks per-task token, enforces budget, writes the ledger |
| Credits Ledger | Portions, 70/80/90% checkpoints, optional loans or house key with caps |
| Agent Runner | One container per task on a per-task clone; harness reaches models only through the proxy |
| Integration Service | Builds `candidate/<run>` from main plus submitted branches |
| Verification Engine | Runs checks per profile, including locked and hidden tests; records exit codes and artifacts |
| Referee | TinyFish drives the running candidate through user journeys and returns a verdict |
| Failure Router | Maps failures to likely task/contract with confidence |
| Merge Service | Only writer to main; requires a recorded human approval; snapshots and tags for undo |
| Job Worker | Runs long operations (sandboxes, builds) asynchronously |

## 3. End-to-End Flow

```
Chat -> Observer -> Spec items (proposed)
     -> humans confirm -> Spec v(n)   (confirmed suggestion = decision item)
     -> Planner -> tasks + contracts (proposed) -> humans approve
     -> per task: context pack -> clone + sandbox -> agent (via model proxy) -> submit + handoff
     -> Integration run: candidate branch = main + task branches
     -> Verification checks (profile: fast | standard | strict)
     -> Referee verdict on the running candidate
          fail -> Failure Router -> owner notified with evidence -> resubmit -> new run
          pass -> human approves (every profile) -> Merge Service -> main (snapshot + tag)
```

## 4. Trust Boundaries

1. **Untrusted:** chat text, repo contents, LLM output, agent code, sandbox containers.
2. **Trusted:** backend services, model proxy, merge service, database, provider keys.

Rules:
- Agents never receive keys and never touch the protected mount.
- Agents write only to their own clone and task branch.
- Only the Merge Service updates main, and only after an approval row exists for the candidate SHA.
- Verdicts are computed from exit codes and artifacts, not agent text.
- LLM outputs are validated against schemas before use.

## 5. Isolation and Network Design

```
Host
 +-- Backend, Model Proxy (trusted; hold keys)
 +-- Docker network "agents" (internal: true; no route to the internet)
      +-- model-proxy endpoint (only reachable service)
      +-- task-12 container  (its own clone; no keys)
      +-- task-13 container  (its own clone; no keys)
 +-- Docker network "mirror"
      +-- candidate build container (fresh per run)
      +-- tunnel so the referee can reach the running candidate
```

Docker has no native domain allowlist, so the allowlist is the internal network: the sandbox can reach only the proxy, and the proxy decides which providers are allowed per workspace.

## 6. Two LLM Paths, One Adapter

```
Platform LLMClient (observer, planner, handoff) --+
                                                   +--> Provider Adapter --> Claude / OpenAI-compatible / Ollama / mock
Sandbox harness --> Model Proxy -------------------+          |
                                                              +--> Credits Ledger
```

## 7. Git Model

- `main`: protected; written only by the Merge Service.
- Per-task clone on branch `task/<task_id>`: a full clone, never a bare worktree linked to the protected repo.
- `candidate/<run_id>`: disposable; main plus task branches merged in dependency order.
- Every approved merge is snapshotted and tagged (`release/<n>`) so it can be undone.

## 8. Knowledge Model (relational first)

Entities: Requirement, Decision, Contract, Task, Submission, Commit, CheckResult, Failure.
Relations: `requirement -> task`, `decision -> contract`, `contract -> task`, `task -> task (depends_on)`, `submission -> commit`, `check_result -> failure -> task`.
Rows are versioned; contracts and confirmed items are append-only. Retrieval walks outgoing links to a depth limit and trims by priority to a token budget.

## 9. Verification Pipeline

```
candidate build
  -> build
  -> locked tests
  -> hidden tests                          (all profiles)
  -> lint, contract conformance            (standard, strict)
  -> dependency scan, secret scan          (standard, strict)
  -> referee smoke journey                 (standard)
  -> referee full journeys                 (strict)
  -> verdict + evidence bundle
  -> human approval                        (every profile)
```

Referee verdicts: `pass`, `app_failure`, `browser_failure`, `service_error`, `inconclusive`, `not_run`. Only `pass` counts as a pass.

## 10. Failure Attribution

1. Parse failing test names and stack traces to files.
2. Map files to the task branches that touched them, and to the component owner.
3. Check whether the failure violates a pinned contract.
4. Produce a ranked suspect list `{task, contract, confidence, rationale}`.
5. Route to the top suspect's owner; show alternates. Low confidence goes to the workspace owner.
6. `browser_failure` and `service_error` are infrastructure issues, not attributed to a task.

## 11. Frontend Structure

- `/` landing: create workspace, accept invite
- `/w/[id]` workspace: chat, spec panel, plan board, runs, referee evidence, credits, approvals
- Roles: owner, member, viewer (read-only)

## 12. Key Decisions (ADRs to write)

- ADR-001: Relational knowledge store before graph DB.
- ADR-002: Reuse an existing coding harness rather than build one.
- ADR-003: Docker per task, per-task clone, internal network.
- ADR-004: Platform-side model proxy; keys never enter sandboxes.
- ADR-005: A human approves every merge in every profile.
- ADR-006: Invites, not room codes, as credentials.

## 13. Evolution Path

SQLite then Postgres; single-node worker then queue and multiple workers; Docker then gVisor/Firecracker; local git then GitHub app integration; Claude first then more providers; fast profile then full strict gates.
