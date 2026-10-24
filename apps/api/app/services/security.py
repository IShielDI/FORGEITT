"""Security checks (stage 20): secret scan and dependency vulnerability scan (standard and strict only).

The secret scan reads the candidate's files (no candidate code runs) and fails on any match.
The dependency scan uses pip-audit without installing anything; when pip-audit is not available it
is reported as skipped, never as passed.
"""

import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

SECRET_PATTERNS = {
    "Anthropic API key": re.compile(r"sk-ant-[A-Za-z0-9_-]{20,}"),
    "OpenAI-style key": re.compile(r"\bsk-[A-Za-z0-9]{32,}\b"),
    "AWS access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "GitHub token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "hard-coded credential": re.compile(
        r"""(?i)\b(api[_-]?key|secret|password|token)\b\s*[:=]\s*["'][A-Za-z0-9_\-/+=]{16,}["']"""
    ),
}
SKIP_DIRS = {".git", "_holdout", "__pycache__", "node_modules", ".pytest_cache"}
SKIP_SUFFIXES = {".png", ".jpg", ".gif", ".mp4", ".db", ".pyc", ".zip", ".ico"}
MAX_FILE_BYTES = 1_000_000


def _files(root: Path):
    for p in root.rglob("*"):
        if (
            p.is_file()
            and not (set(p.relative_to(root).parts) & SKIP_DIRS)
            and p.suffix not in SKIP_SUFFIXES
            and p.stat().st_size <= MAX_FILE_BYTES
        ):
            yield p


def find_secrets(root: Path) -> list[str]:
    """Findings as 'path:line: kind' (the matched value itself is never logged)."""
    hits = []
    for f in _files(root):
        try:
            lines = f.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for n, line in enumerate(lines, 1):
            for kind, rx in SECRET_PATTERNS.items():
                if rx.search(line):
                    hits.append(f"{f.relative_to(root).as_posix()}:{n}: {kind}")
    return hits


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
    from app.services.verify import _record as record

    return record(name, kind, command, code, ms, log, log_dir, status)


def secret_scan(m, log_dir: Path) -> dict[str, Any]:
    t0 = time.monotonic()
    hits = find_secrets(m.path)
    log = "\n".join(hits) if hits else "no secrets found"
    return _record(
        "secret_scan",
        "secret_scan",
        "forgeit secret-scan .",
        1 if hits else 0,
        int((time.monotonic() - t0) * 1000),
        log,
        log_dir,
    )


def dependency_scan(m, log_dir: Path) -> dict[str, Any]:
    req = m.path / "requirements.txt"
    if not req.exists():
        return _record(
            "dependency_scan",
            "dependency_scan",
            "(no requirements.txt)",
            None,
            0,
            "",
            log_dir,
            status="skipped",
        )
    if importlib.util.find_spec("pip_audit") is None:
        return _record(
            "dependency_scan",
            "dependency_scan",
            "pip-audit",
            None,
            0,
            "pip-audit is not installed on the host",
            log_dir,
            status="skipped",
        )
    # --no-deps --disable-pip: audit the listed pins only; nothing is installed or executed
    argv = [
        sys.executable,
        "-m",
        "pip_audit",
        "--no-deps",
        "--disable-pip",
        "-r",
        str(req),
        "--format",
        "json",
    ]
    t0 = time.monotonic()
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=180)
        out, code = r.stdout + r.stderr, r.returncode
    except subprocess.TimeoutExpired:
        out, code = "pip-audit timed out", 124
    ms = int((time.monotonic() - t0) * 1000)
    try:
        report = json.loads(r.stdout) if code in (0, 1) else None
        vulns = [d for d in (report or {}).get("dependencies", []) if d.get("vulns")]
        if report is not None:
            code = 1 if vulns else 0
            out = (
                "\n".join(
                    f"{d['name']} {d.get('version', '')}: {', '.join(v['id'] for v in d['vulns'])}"
                    for d in vulns
                )
                or "no known vulnerabilities"
            )
    except (ValueError, NameError):
        pass
    return _record(
        "dependency_scan",
        "dependency_scan",
        "pip-audit --no-deps --disable-pip -r requirements.txt",
        code,
        ms,
        out,
        log_dir,
    )
