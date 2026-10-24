# PRD: ForgeIt

Status: Draft v2 (review fixes applied) | Owner: Team | Source: `docs/source/product-vision.docx`

*Forged by agents. Checked by a referee.*

## 1. Summary
ForgeIt is a shared engineering workspace where a team discusses a product, an observing agent turns the discussion into a living specification, the platform plans and assigns tasks, each teammate builds with their own coding agent in isolation, and the combined work is verified in a mirror environment before a human approves a merge into the protected main project.

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
- **Roles:** Owner (creates workspace, approves merges), Member (owns tasks), Viewer (read-only).

## 6. User Journeys
1. Create workspace, send single-use invite links, teammates join.
2. Discuss in chat; see suggestions vs confirmed decisions populate the spec.
3. Approve the spec; review the proposed plan, owners, dependencies, contracts.
4. Each member starts their task; their agent works in an isolated environment and submits a handoff.
5. Platform builds a candidate in the mirror, runs checks, shows evidence.
6. On failure, the owner receives evidence and resubmits.
7. A referee verdict and check results are shown; a human approves the merge to protected main (every profile; there is no auto-merge).

## 7. Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| F1 | Create workspace; join via single-use invite link or per-member token (a room code is a name, not a credential) | P0 |
| F2 | Realtime group chat with message history | P0 |
| F3 | Observer agent extracts requirements; classifies each as suggestion or decision | P0 |
| F4 | Editable living spec with explicit human confirm; a confirmed suggestion becomes a decision item | P0 |
| F5 | Planner proposes tasks, owners, dependencies, component boundaries | P0 |
| F6 | Shared contracts (API, DB schema, types) defined and versioned before coding | P0 |
| F7 | Versioned project knowledge store linking requirements, decisions, tasks, code changes, test results | P0 (relational), P2 (graph) |
| F8 | Task-scoped context retrieval for agents | P0 |
| F9 | Isolated per-task agent environment: its own clone and branch, no model keys, models reached only through the platform proxy | P0 |
| F10 | Agent handoff summary on submission | P1 |
| F11 | Mirror integration build combining submitted branches | P0 |
| F12 | Automated build, test, lint, contract checks | P0 |
| F13 | Security checks (dependency and secret scan) | P1 |
| F14 | Failure routing with evidence and confidence level | P0 |
| F15 | A human approves every merge in every profile; protected main; snapshot and undo | P0 |
| F16 | Verification profiles (fast, standard, strict) that change how much verification runs, never who approves | P1 |
| F17 | Referee (TinyFish) drives the running candidate through user journeys; verdicts: pass, app_failure, browser_failure, service_error, inconclusive, not_run | P0 |
| F18 | Locked tests (agents cannot edit) and hidden tests written by a human after the first build | P0 |
| F19 | Credits ledger: per-member portions, 70/80/90% checkpoints, optional loans, optional house key with caps | P0 |
| F20 | Platform model proxy holding keys and enforcing budget; two LLM paths share one provider adapter | P0 |
| F21 | Finale demo loop: task, agent run, mirror, referee verdict, human approval in one scripted path | P0 |
| F22 | Extra providers (OpenAI-compatible group) after Claude, allowed per workspace | P1 |

## 8. Non-Functional Requirements
- Agents never write to main directly; enforced by branch protection plus server checks.
- Every spec change, decision, and verdict is traceable (who, when, why, version).
- Verification verdicts come from command exit codes and artifacts, never agent claims.
- Sandbox: no host access, resource limits, no model keys; its only network route is the platform model proxy on an internal Docker network.
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
| Scope creep | Stage-gated roadmap in BUILD_PROMPTS.md |

## 11. Release Plan
- **Finale slice / MVP (stages 0 to 18):** invites, chat, spec, plan, agents via model proxy, mirror, checks, locked and hidden tests, referee, routing, human merge, finale demo loop.
- **Later (stages 19 onward):** verification profiles, security scans, referee journeys from requirements, hidden-test authoring workflow, demo polish, house key and extra providers, graph retrieval.

## 12. Open Questions
- Finale rules: is pre-built code allowed, and what is the date and format?
- House key: dollar cap per workspace and per person? May it be stored on the host laptop?
- Which providers first after Claude?
- Which teammate writes and approves the hidden QA tests?
- How much RAM does the host laptop have? (Docker Desktop needs at least 8 GB.)
- Which coding harness to wrap first, and are target repos monorepo-only for the MVP?
