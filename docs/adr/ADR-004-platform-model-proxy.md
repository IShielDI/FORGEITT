# ADR-004: Keys never enter sandboxes; the platform makes model calls

**Status:** accepted

**Context.** Agents must never receive keys (AGENTS invariants). The docs describe a model proxy on an internal Docker network.

**Decision.** The agent loop runs in the backend. The sandbox only executes the tool commands the model asks for, with `--network none`. The backend, acting as the model proxy, holds the keys (members' keys Fernet-encrypted at rest; the provider and house keys in the backend environment), picks the paying key (own portion, then loan, then the capped house key), enforces the budget and the 70/80/90/100% checkpoints, and writes every call to the ledger. Platform calls (observer, planner, handoff, journeys) go through the same provider adapter and ledger (`app/llm`).

**Consequences.** No key or proxy token ever exists inside a container. A harness that must call the model from inside the sandbox would need a real proxy endpoint on an internal network; that is not built.
