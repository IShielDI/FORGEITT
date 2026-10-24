# ADR-006: Invites and per-member tokens, not room codes, as credentials

**Status:** accepted

**Context.** A shared room code leaks easily and cannot be revoked per person.

**Decision.** A workspace has a display name and slug only. People join with single-use invite links (7-day expiry, stored as SHA-256 hashes, mailed through Gmail SMTP when configured, otherwise shown once to the owner). Accepting an invite creates a member with their own login token, shown once and stored as a hash. Roles are owner, member and viewer (read-only).

**Consequences.** Each person is accountable and can be removed. Losing a token means asking the owner for a new invite. Live streams pass the token as a query parameter because browsers cannot set headers there, so keep logs private.
