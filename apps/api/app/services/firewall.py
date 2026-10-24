"""Layered firewall. Layers 1 (read-only mount) and 4 (clean checkout) live in workspace/mirror code;
this module is layer 2 (commit-time check), the action-time rule check, and the attempt log."""

import re
import subprocess

from app.core import config, db

PROTECTED_PREFIXES = ("protected/", "holdout/", "journeys/")
TEST_CONFIG_NAMES = {
    "conftest.py",
    "pytest.ini",
    "tox.ini",
    "setup.cfg",
    "pyproject.toml",
    ".coveragerc",
}


def is_protected(path: str) -> bool:
    p = path.lstrip("./")
    base = p.rsplit("/", 1)[-1]
    return p.startswith(PROTECTED_PREFIXES) or base in TEST_CONFIG_NAMES


def commit_check(repo: str, base: str, branch: str):
    """Reject any change, delete or rename touching a protected path, and any new conftest.py anywhere."""
    out = subprocess.run(
        ["git", "diff", "--name-status", "-M", f"{base}...{branch}"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    bad = []
    for line in out.splitlines():
        parts = line.split("\t")
        status, paths = parts[0], parts[1:]
        for p in paths:
            if is_protected(p):
                bad.append({"status": status, "path": p})
    return bad


BOOTSTRAP_ALLOWED = ("protected/tests/", "protected/contracts/contracts.json")


def bootstrap_check(repo: str, base: str, branch: str):
    """The bootstrap change may add the first tests and spec, but not touch platform-owned files
    (pytest settings, the part map, hold-out or journeys) and may not delete existing protected files."""
    out = subprocess.run(
        ["git", "diff", "--name-status", "-M", f"{base}...{branch}"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    bad = []
    for line in out.splitlines():
        parts = line.split("\t")
        status, paths = parts[0], parts[1:]
        for p in paths:
            if not is_protected(p) or p.startswith(BOOTSTRAP_ALLOWED):
                continue
            bad.append({"status": status, "path": p})
    return bad


# Reaching above the workspace (any ".." path component) or naming the platform's own folders. In a plain-subprocess
# sandbox this is a speed bump, not a wall (a script can build the path itself): Docker is the real isolation.
_UP_RE = re.compile(r"(?:^|[^\w.])\.\.(?:[/\\]|$|[^\w.])")


def escapes(cmd: str) -> bool:
    return (
        bool(_UP_RE.search(cmd))
        or any(str(p) in cmd for p in (config.DATA, config.STATE))
        or bool(re.search(r"secret\.key|platform\.db|/proc/|/\.ssh|\.env\b", cmd))
    )


_WRITE_VERBS = re.compile(
    r"(\btee\b|\bsed\s+-i|\brm\b|\bmv\b|\bcp\b|\btouch\b|\bchmod\b|\bgit\s+(checkout|restore|reset|rm|mv)\b|\bpython3?\s+-c\b|\bperl\b|\bdd\b|\binstall\b)"
)
_PROT_RE = re.compile(
    r"(protected|holdout|journeys)(/|\b)|conftest\.py|pytest\.ini|tox\.ini|setup\.cfg|\.coveragerc"
)


def check_action(tool: str, args: dict, room_id: int, agent: str, bootstrap: bool = False):
    """Returns None if allowed, else a message for the agent. Blocked attempts are logged.
    In a bootstrap run protected paths are writable (the commit-time bootstrap_check and the human review guard them),
    but escaping the workspace is still blocked."""
    if bootstrap:
        path, cmd = args.get("path", ""), args.get("command", "")
        if (tool == "bash" and escapes(cmd)) or (tool != "bash" and ".." in path):
            return _block(room_id, agent, "bootstrap-escape", (cmd or path)[:200])
        return None
    if tool == "bash":
        cmd = args.get("command", "")
        # Conservative on purpose: within one pipeline segment, a mutating verb plus a protected path is blocked,
        # as is any attempt to reach above the workspace. Harmless redirects (2>&1, >/dev/null) are ignored,
        # so running the visible tests (which reads protected/pytest.ini) stays allowed.
        clean = re.sub(r"\d*>&\d+|\d*>>?\s*/dev/null", " ", cmd)
        for seg in re.split(r"&&|\|\||;|\||\n", clean):
            if _PROT_RE.search(seg) and _WRITE_VERBS.search(seg):
                return _block(room_id, agent, "bash", cmd[:200])
            if any(
                is_protected(t) for t in re.findall(r">>?\s*(\S+)", seg)
            ):  # redirect INTO a protected path
                return _block(room_id, agent, "bash", cmd[:200])
        if escapes(cmd):
            return _block(room_id, agent, "bash", cmd[:200])
    else:
        path = args.get("path", "")
        cmd = args.get("command", "")
        if cmd != "view" and (is_protected(path) or ".." in path):
            return _block(room_id, agent, f"edit:{cmd}", path)
    return None


def _block(room_id, agent, action, path):
    db.ex(
        "INSERT INTO attempts(room_id,agent,action,path,ts) VALUES(?,?,?,?,?)",
        (room_id, agent, action, path, db.now()),
    )
    return (
        "BLOCKED: that action touches protected files (tests, test settings, contracts). "
        "Do not work around this. If a test looks wrong, stop and file a contract-change request instead."
    )
