# PRD: AI-Native Collaborative Coding Workspace

Status: Draft v1 | Owner: Team | Source: `docs/source/product-vision.docx`

## 1. Summary
A shared engineering workspace where a team discusses a product, an observing agent turns the discussion into a living specification, the platform plans and assigns tasks, each teammate builds with their own coding agent in isolation, and the combined work is verified in a mirror environment before a human approves a merge into the protected main project.

## 2. Problem
- Team discussions live in chat; AI coding happens in separate private chats. Context is duplicated and diverges.
- Parallel agents make conflicting assumptions (API shapes, schemas, types).
- Agents report "done" without proof; integration failures appear late and blame is unclear.
- Unverified AI-written code reaches the main branch.

## 3. Goals
1. One shared source of project truth that every agent reads from.
2. Parallel work against agreed contracts, with isolation.
3. Verification based on real command output and observable behavior.
4. Failures routed to the likely owner with evidence.
5. Human approval as the final gate to main.

## 4. Non-Goals (MVP)
- Replacing the IDE or building a new coding agent from scratch (reuse an existing harness).
- Full knowledge-graph database (start relational with typed links).
- Multi-cloud deployment, enterprise SSO, billing.
- Autonomous merge without human approval (never).

## 5. Users and Personas
- **Hackathon team (primary MVP):** 2 to 6 people, fast and light verification.
- **Product team (later):** stricter gates, security checks, deployment validation.
- **Roles:** Owner (creates workspace, approves merges), Member (owns tasks), Observer (read-only).

## 6. User Journeys
1. Create workspace, share room ID, teammates join.
2. Discuss in chat; see suggestions vs confirmed decisions populate the spec.
3. Approve the spec; review the proposed plan, owners, dependencies, contracts.
4. Each member starts their task; their agent works in an isolated environment and submits a handoff.
5. Platform builds a candidate in the mirror, runs checks, shows evidence.
6. On failure, the owner receives evidence and resubmits.
7. On pass, a human reviews and approves the merge to protected main.

## 7. Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| F1 | Create/join workspace via room ID | P0 |
| F2 | Realtime group chat with message history | P0 |
| F3 | Observer agent extracts requirements; classifies each as suggestion or decision | P0 |
| F4 | Editable living spec with explicit human confirm for decisions | P0 |
| F5 | Planner proposes tasks, owners, dependencies, component boundaries | P0 |
| F6 | Shared contracts (API, DB schema, types) defined and versioned before coding | P0 |
| F7 | Versioned project knowledge store linking requirements, decisions, tasks, code changes, test results | P0 (relational), P2 (graph) |
| F8 | Task-scoped context retrieval for agents | P0 |
| F9 | Isolated per-task agent environment on its own branch | P0 |
| F10 | Agent handoff summary on submission | P1 |
| F11 | Mirror integration build combining submitted branches | P0 |
| F12 | Automated build, test, lint, contract checks | P0 |
| F13 | Security checks (dependency and secret scan) | P1 |
| F14 | Failure routing with evidence and confidence level | P0 |
| F15 | Human approval gate; protected main; rollback via history/tags | P0 |
| F16 | Adaptive verification profiles (light, standard, strict) | P1 |
| F17 | Browser-based testing agent running user journeys | P2 |
| F18 | Hidden/protected tests | P2 |

## 8. Non-Functional Requirements
- Agents never write to main directly; enforced by branch protection plus server checks.
- Every spec change, decision, and verdict is traceable (who, when, why, version).
- Verification verdicts come from command exit codes and artifacts, never agent claims.
- Sandbox: no host access, resource limits, no secrets passed into agent containers.
- Works on free tiers; demo path reproducible offline except for the LLM.

## 9. Success Metrics
- Time from approved spec to first integrated candidate.
- Share of integration failures routed to the correct owner (manual audit).
- Number of unverified changes reaching main (target: 0).
- Demo: end-to-end flow completes on the sample app.

## 10. Risks
| Risk | Mitigation |
|------|-----------|
| LLM misclassifies suggestion vs decision | Human confirm required; show source message |
| Wrong failure attribution | Report confidence and alternates, not certainty |
| Free-tier rate limits | Provider abstraction, caching, recorded demo |
| Agent escapes or leaks | Container isolation, no secrets, network limits |
| Scope creep | Stage-gated roadmap in BUILD_PROMPTS.md (repo root) |

## 11. Release Plan
- **MVP (stages 0 to 18):** chat, spec, plan, agents, mirror, checks, routing, human merge.
- **v1:** adaptive profiles, browser testing agent, hidden tests, graph retrieval.

## 12. Open Questions
- Which coding harness to wrap first (Aider vs OpenHands vs opencode)?
- Monorepo-only targets for MVP, or arbitrary repos?
