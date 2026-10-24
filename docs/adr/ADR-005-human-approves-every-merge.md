# ADR-005: A human approves every merge, in every profile

**Status:** accepted

**Context.** Unverified AI-written code must not reach main (PRD goal 5).

**Decision.**
- Only the Merge Service (`gitops.merge_branches`) may move `main`. A `reference-transaction` hook rejects any other update, including pushes from clones.
- Merging requires a call by the workspace owner. The approval is bound to the exact commit that was verified: a branch that moved after verification is refused as stale.
- Every merge is snapshotted, tagged `release/<n>`, and can be undone.
- Profiles (fast, standard, strict) change only which checks run. Strict additionally refuses any non-pass referee verdict.

**Consequences.** There is no auto-merge path to maintain or to exploit. Throughput depends on people approving.
