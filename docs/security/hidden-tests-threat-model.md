# Hidden tests: threat model

Hidden tests stop an agent from passing a change by tailoring its code to the visible (locked) tests. This note lists what they protect against, how, and what is not covered.

## Assets
- The source of each hidden test, and the fact of what it checks.
- The integrity of the verdict: a change that only satisfies the visible tests must fail.

## Who could leak or weaken them
| Actor | Threat |
|---|---|
| A coding agent in its sandbox | Reads the hidden tests, or hard-codes their answers |
| Agent-written code running in the mirror | Reads the hidden tests at verify time and adapts its behaviour |
| A model prompt or log | Echoes test source into a place agents or teammates later read |
| One teammate alone | Writes a weak hidden test, or one that leaks the answers to the visible tests |

## Controls
- **Storage outside every agent path.** Drafts live in `<GIT_STORAGE_PATH>/rooms/<id>/holdout_drafts/` and approved tests in `.../holdout/`. Neither is inside the protected repo, a per-task clone, or anything mounted into an agent container. Agents run with only their own clone mounted and no network.
- **Mounted only at verify time.** The mirror copies `holdout/` into its throwaway build (`_holdout/`) after merging, runs it as a separate pytest suite, and deletes the mirror afterwards.
- **Never served or logged.** The API returns file names, authors, approvers, status and test function names only. The hidden suite's raw pytest output is never saved; its check log records only "n/m hidden tests passed". The UI shows pass/fail and failure messages. Hidden tests are never put into prompts or shared memory.
- **Two people.** A named teammate writes the test after the first build, and a *different* person approves it (`POST /api/rooms/{id}/holdout/{file}/approve`). The author cannot approve their own test. Only approved tests run.
- **Firewall.** Agents' edits to `holdout/` or test configuration are blocked, and the commit-time check rejects changes touching protected paths.

## Known gaps
- In **host** mirror mode (no Docker image), candidate code runs on the host and could read files next to the mirror. Use the `forgeit-mirror` image (docker mode) for real runs; every result records which mode ran.
- Within one mirror run, code under test can in principle inspect the hidden test files in `_holdout/` of that same throwaway build. Container isolation limits this to the current candidate only.
- Failure messages may quote an assertion expression. Keep secrets and full expected values out of assertion messages.
- The approver cannot read the source in the UI. Review happens out of band (the author shares the file privately), and the approval records who vouched for it.
