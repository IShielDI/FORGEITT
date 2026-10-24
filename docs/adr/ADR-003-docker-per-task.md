# ADR-003: Docker per task, per-task clone, and a containerised mirror

**Status:** accepted

**Context.** Agents run model-chosen commands, and candidate code runs hidden tests (TRD R3, R5).

**Decision.** Each agent command runs in a fresh `forgeit-agent` container: no network, all capabilities dropped, memory/CPU/PID limits, non-root, only the task's own full clone mounted, and `protected/` mounted read-only. Without Docker or the image, real model runs are refused (`ALLOW_UNSAFE_SANDBOX` is for throwaway machines only). The mirror runs tests in `forgeit-mirror` containers with no network, and the candidate app in its own container published on 127.0.0.1. Host mode is a labelled fallback.

**Consequences.** A real isolation boundary on a laptop with Docker Desktop. Docker has no domain allowlist, so the sandbox simply has no network: model calls happen in the backend (ADR-004). The running mirror app can reach the internet through the default bridge; tests cannot.
