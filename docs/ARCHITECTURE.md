# Architecture

## 1. System Overview

```
 Browser (Next.js)
   | HTTP + WebSocket
   v
 FastAPI Backend ------------------------------+
   |-- Chat Service                            |
   |-- Observer (LLM) --> Spec Service         |
   |-- Planner (LLM)  --> Task/Contract Svc    |
   |-- Knowledge Store + Context Retriever     |
   |-- Agent Runner  ---> Docker sandboxes     |
   |-- Integration Service --> Mirror build    |
   |-- Verification Engine (checks)            |
   |-- Failure Router                          |
   |-- Merge Service (human gate)              |
   v                                           |
 PostgreSQL                                    |
 Git storage: main (protected), task/*, candidate/*
 Artifact store (logs, screenshots)  <---------+
```

## 2. Components

| Component | Responsibility |
|-----------|----------------|
| Chat Service | Rooms, membership, message persistence, realtime fan-out |
| Observer | Reads new messages, emits structured spec proposals (suggestion/decision/requirement/question) |
| Spec Service | Versioned spec; confirm/reject/edit; snapshots |
| Planner | Proposes tasks, owners, dependencies, components, contracts |
| Contract Registry | Versioned API/schema/type contracts agents must follow |
| Knowledge Store | Typed, versioned links: requirement, decision, contract, task, commit, check result |
| Context Retriever | Builds a task-scoped, budgeted context pack with item citations |
| Agent Runner | Starts a sandbox per task, mounts a worktree, runs the coding harness, collects handoff |
| Integration Service | Builds `candidate/<run>` from main plus submitted branches |
| Verification Engine | Runs checks per profile; records exit codes and artifacts |
| Failure Router | Maps failures to likely task/contract with confidence |
| Merge Service | Only writer to main; requires recorded human approval; tags releases |
| Job Worker | Runs long operations (sandbox, builds) asynchronously |

## 3. End-to-End Flow

```
Chat -> Observer -> Spec items (proposed)
     -> humans confirm -> Spec v(n)
     -> Planner -> tasks + contracts (proposed) -> humans approve
     -> per task: context pack -> sandbox + branch -> agent -> submit + handoff
     -> Integration run: candidate branch = main + task branches
     -> Verification checks (build, test, lint, contract, security, browser)
          pass -> human review -> approve -> Merge Service -> main (tagged)
          fail -> Failure Router -> owner notified with evidence -> resubmit -> new run
```

## 4. Trust Boundaries

1. **Untrusted:** chat text, repo contents, LLM output, agent code.
2. **Semi-trusted:** sandbox containers (limited, disposable).
3. **Trusted:** backend services, merge service, database.

Rules:
- Agents have write access only to their task branch inside their sandbox.
- Only the Merge Service pushes to main, and only after an approval row exists for the run's exact candidate SHA.
- Verification verdicts are computed by the backend from exit codes, not agent text.
- LLM outputs are validated against schemas before use.

## 5. Isolation Design

```
Host
 +-- Backend (trusted)
 +-- Docker network "agents" (egress allowlist: LLM API only)
      +-- task-12 container  (worktree: task/12, no secrets)
      +-- task-13 container  (worktree: task/13)
 +-- Docker network "mirror" (no egress except package mirrors if configured)
      +-- candidate build container (fresh per run)
```

## 6. Git Model

- `main`: protected; written only by the Merge Service.
- `task/<task_id>`: one per task, created from main at start time (or from a dependency's branch when explicitly chained).
- `candidate/<run_id>`: disposable; created from main, task branches merged in dependency order.
- Tags: `release/<n>` on every approved merge for rollback.

## 7. Knowledge Model (relational first)

Entities: Requirement, Decision, Contract, Task, Submission, Commit, CheckResult, Failure.
Relations: `requirement -> task`, `decision -> contract`, `contract -> task`, `task -> task (depends_on)`, `submission -> commit`, `check_result -> failure -> task`.
Every row carries a version; contracts and confirmed items are append-only. Retrieval walks outgoing links from a task up to a depth limit and trims by priority to fit a token budget. A graph database can replace this later without changing the retriever interface.

## 8. Verification Pipeline

```
candidate build
  -> install/build
  -> unit tests
  -> lint/type check
  -> contract conformance
  -> dependency + secret scan   (standard/strict)
  -> browser journeys           (strict)
  -> hidden tests               (strict)
  -> verdict + evidence bundle
```

Evidence bundle: command, exit code, logs, screenshots/trace, reproduction steps.

## 9. Failure Attribution

1. Parse failing test names and stack traces to files.
2. Map files to the task branches that touched them, and to the component owner.
3. Check whether the failure violates a pinned contract.
4. Produce a ranked suspect list `{task, contract, confidence, rationale}`.
5. Route to the top suspect's owner; show alternates. Low confidence goes to the workspace owner for triage.

## 10. Frontend Structure

- `/` landing, create/join
- `/w/[id]` workspace: chat, spec panel, plan board, runs, approvals
- Panels: **Chat**, **Spec** (suggestion vs decision badges), **Plan** (tasks, deps, contracts), **Runs** (checks, evidence), **Approval**

## 11. Key Decisions (ADRs to write)

- ADR-001: Relational knowledge store before graph DB.
- ADR-002: Reuse an existing coding harness rather than build one.
- ADR-003: Docker per task for isolation.
- ADR-004: Backend-owned git with protected main; GitHub sync optional.
- ADR-005: Human approval is mandatory for every merge.

## 12. Evolution Path

MVP relational store, then graph retrieval; single-node worker, then queue and multiple workers; Docker, then Firecracker/gVisor; local git, then GitHub app integration; light profile, then full strict gates.
