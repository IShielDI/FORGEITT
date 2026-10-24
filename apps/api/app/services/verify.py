"""Verification engine (stage 16): a registry of checks run against the mirror.

Each check records its command, exit code, duration, status and a log file. The verdict is computed
only from exit codes, never from what an agent says. Hidden test results show pass/fail and failure
messages; their source never leaves the mirror.

Profiles (stage 19) pick which checks run: fast runs build and tests; standard and strict add lint,
contract conformance and the security scans.
"""

import json
import re
from pathlib import Path
from typing import Any

from app.core.db import q, q1
from app.services.gitops import room_dir

PROFILES: dict[str, tuple[str, ...]] = {
    "fast": ("build", "locked_tests", "hidden_tests"),
    "standard": (
        "build",
        "locked_tests",
        "hidden_tests",
        "lint",
        "contract",
        "dependency_scan",
        "secret_scan",
    ),
    "strict": (
        "build",
        "locked_tests",
        "hidden_tests",
        "lint",
        "contract",
        "dependency_scan",
        "secret_scan",
    ),
}
LINT_SELECT = "E9,F63,F7,F82"  # syntax errors and undefined names: real breakage, not style


def profile_of(room_id: int) -> str:
    from app.core import config

    row = q1("SELECT verification_profile FROM rooms WHERE id=?", (room_id,))
    p = (row or {}).get("verification_profile") or config.VERIFICATION_PROFILE
    return p if p in PROFILES else "fast"


def _record(
    name: str,
    kind: str,
    command: str,
    code: int | None,
    ms: int,
    log: str,
    log_dir: Path,
    status: str | None = None,
) -> dict[str, Any]:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / f"{name}.log"
    path.write_text(log or "", encoding="utf-8")
    if status is None:
        status = "passed" if code == 0 else "failed"
    return {
        "name": name,
        "kind": kind,
        "command": command,
        "exit_code": code,
        "duration_ms": ms,
        "status": status,
        "log_path": str(path),
    }


def _pinned_api_paths(room_id: int) -> dict[str, set[str]]:
    """Paths and methods declared by approved API contracts (OpenAPI-style JSON content)."""
    want: dict[str, set[str]] = {}
    for c in q(
        "SELECT content FROM contracts WHERE room_id=? AND kind='api' AND status='approved'",
        (room_id,),
    ):
        try:
            doc = json.loads(c["content"])
        except (TypeError, ValueError):
            continue
        for path, ops in (doc.get("paths") or {}).items() if isinstance(doc, dict) else []:
            want.setdefault(path, set()).update(
                m.lower() for m in (ops or {}) if isinstance(m, str)
            )
    return want


def check_build(m, log_dir: Path) -> dict[str, Any]:
    argv = ["python", "-m", "compileall", "-q", "app"]
    code, out, ms = m.exec(argv)
    return _record("build", "build", " ".join(argv), code, ms, out, log_dir)


def check_lint(m, log_dir: Path) -> dict[str, Any]:
    argv = ["python", "-m", "ruff", "check", "--select", LINT_SELECT, "--no-cache", "app"]
    code, out, ms = m.exec(argv)
    if code != 0 and re.search(r"No module named ruff", out):
        return _record("lint", "lint", " ".join(argv), None, ms, out, log_dir, status="skipped")
    return _record("lint", "lint", " ".join(argv), code, ms, out, log_dir)


OPENAPI_SNIPPET = "import json, app.main as m; print(json.dumps(m.app.openapi()))"


def check_contract(m, room_id: int, log_dir: Path) -> dict[str, Any]:
    want = _pinned_api_paths(room_id)
    argv = ["python", "-c", OPENAPI_SNIPPET]
    if not want:
        return _record(
            "contract",
            "contract",
            "(no approved API contract)",
            None,
            0,
            "",
            log_dir,
            status="skipped",
        )
    code, out, ms = m.exec(argv)
    if code != 0:
        return _record("contract", "contract", " ".join(argv), code, ms, out, log_dir)
    try:
        spec = json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return _record(
            "contract",
            "contract",
            " ".join(argv),
            1,
            ms,
            "could not read the app's OpenAPI\n" + out,
            log_dir,
        )
    have = {p: {k.lower() for k in ops} for p, ops in (spec.get("paths") or {}).items()}
    missing = [
        f"{meth.upper()} {p}"
        for p, meths in want.items()
        for meth in meths
        if meth not in have.get(p, set())
    ]
    missing += [f"ANY {p}" for p, meths in want.items() if not meths and p not in have]
    log = (
        "missing from the candidate:\n" + "\n".join(missing)
        if missing
        else "all pinned paths present"
    )
    return _record("contract", "contract", " ".join(argv), 1 if missing else 0, ms, log, log_dir)


def run(room_id: int, m, change_id: int, profile: str | None = None) -> dict[str, Any]:
    """Run the profile's checks on a merged mirror. Returns the tests (for the UI and routing),
    the per-check evidence, and `passed` computed from exit codes alone."""
    from app.services import security  # stage 20

    profile = profile or profile_of(room_id)
    wanted = PROFILES[profile]
    log_dir = room_dir(room_id) / "evidence" / "checks" / str(change_id)
    checks: list[dict[str, Any]] = []
    if "build" in wanted:
        checks.append(check_build(m, log_dir))
    tests = m.run_tests()
    suites = tests.get("suites", {})
    locked = suites.get("locked", {"exit_code": 1, "duration_ms": 0})
    checks.append(
        _record(
            "locked_tests",
            "locked_test",
            "python -m pytest protected/tests",
            locked["exit_code"],
            locked["duration_ms"],
            tests["log"],
            log_dir,
        )
    )
    hidden = [t for t in tests["tests"] if t["hidden"]]
    if "hidden" in suites:
        note = f"{sum(t['passed'] for t in hidden)}/{len(hidden)} hidden tests passed (sources are not shown)"
        checks.append(
            _record(
                "hidden_tests",
                "hidden_test",
                "python -m pytest _holdout",
                suites["hidden"]["exit_code"],
                suites["hidden"]["duration_ms"],
                note,
                log_dir,
            )
        )
    else:
        checks.append(
            _record(
                "hidden_tests",
                "hidden_test",
                "(none written yet)",
                None,
                0,
                "",
                log_dir,
                status="skipped",
            )
        )
    if "lint" in wanted:
        checks.append(check_lint(m, log_dir))
    if "contract" in wanted:
        checks.append(check_contract(m, room_id, log_dir))
    if "dependency_scan" in wanted:
        checks.append(security.dependency_scan(m, log_dir))
    if "secret_scan" in wanted:
        checks.append(security.secret_scan(m, log_dir))
    # verdict: every check that ran must have exited 0 (skipped checks are shown, not counted)
    passed = (
        all(c["exit_code"] == 0 for c in checks if c["status"] != "skipped") and tests["passed"]
    )
    return {**tests, "passed": passed, "checks": checks, "profile": profile}
