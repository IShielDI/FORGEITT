# ADR-001: Relational knowledge store before a graph database

**Status:** accepted

**Context.** Agents need task-scoped context that traces back to requirements, decisions and contracts (PRD F7, F8). A graph database fits the shape, but it adds a service to run and learn.

**Decision.** Store typed, versioned links in a SQLite table (`knowledge_links`) and walk them in code (`app/services/knowledge.py`), with explicit hops for tracing and a depth limit for general traversal. Context packs (`app/services/context.py`) are built from these links with priority trimming and citations.

**Consequences.** No extra infrastructure, and the data is easy to inspect. Deep or fuzzy queries are limited. The retriever interface (`trace_task`, `traverse`, `context.build`) can move to a graph store later without changing callers.
