# ADR-002: Reuse an existing harness and the existing platform code

**Status:** accepted

**Context.** Building a coding agent from scratch is a non-goal (PRD §4). A working platform ("Referee") already existed, with a step loop, firewall, mirror, referee and ledger.

**Decision.** Keep the Claude tool-use loop (`bash` and the text editor tool) from the existing code as the harness (`app/services/agent_runner.py`). Port the existing platform as-is, then add only the missing stages (AGENTS rule 8). Scripted providers stand in for models in tests.

**Consequences.** Fast progress and battle-tested pieces. The harness speaks only Anthropic's tool API today; OpenAI-compatible providers serve the platform's own calls (observer, planner, handoff), not the sandbox loop. Ported modules carry scoped lint and type exemptions (`TODO(stage-12..18)`) until they are hardened.
