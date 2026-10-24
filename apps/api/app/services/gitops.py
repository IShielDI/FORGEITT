import os
import shutil
import stat
import subprocess
from pathlib import Path

from app.core.config import DATA, SAMPLE


def git(cwd, *args, check=True):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r


def room_dir(room_id) -> Path:
    return DATA / "rooms" / str(room_id)


def original(room_id) -> Path:
    return room_dir(room_id) / "original"


def init_original(room_id, template: Path = SAMPLE):
    o = original(room_id)
    if o.exists():
        return o
    o.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        template, o, ignore=shutil.ignore_patterns("__pycache__", "*.db", ".pytest_cache")
    )
    git(o, "init", "-q", "-b", "main")
    git(o, "config", "user.email", "platform@forgeit.local")
    git(o, "config", "user.name", "Platform")
    git(o, "add", "-A")
    git(o, "commit", "-q", "-m", "Initial original")
    return o


BLANK_MAP = {
    "parts": {"app": {"paths": ["app/"], "owner": "", "depends_on": []}},
    "handler_to_part": {},
    "test_to_part": {},
    "journeys": {},
}


def init_blank(room_id):
    """A fresh project: only the platform-owned skeleton. The first human-approved bootstrap change fills in the
    spec (contracts.json), the locked tests and the first version of the app, and becomes the original."""
    import json

    o = original(room_id)
    if o.exists():
        return o
    (o / "protected/tests").mkdir(parents=True)
    (o / "protected/contracts").mkdir(parents=True)
    (o / "app").mkdir()
    (o / "protected/pytest.ini").write_text(
        "[pytest]\ntestpaths = protected/tests\npythonpath = .\n"
    )
    (o / "protected/contracts/contracts.json").write_text("{}\n")
    (o / "protected/contracts/map.json").write_text(json.dumps(BLANK_MAP, indent=2) + "\n")
    (o / "protected/tests/.gitkeep").write_text("")
    (o / "app/__init__.py").write_text("")
    (o / ".gitignore").write_text("__pycache__/\n*.db\n.pytest_cache/\n")
    git(o, "init", "-q", "-b", "main")
    git(o, "config", "user.email", "platform@forgeit.local")
    git(o, "config", "user.name", "Platform")
    git(o, "add", "-A")
    git(o, "commit", "-q", "-m", "Blank original")
    return o


def make_workspace(room_id, agent, bootstrap=False) -> Path:
    """Clone of the original, own branch, protected/ made read-only (effective for non-root users, e.g. in Docker).
    A bootstrap workspace leaves protected/ writable: it is how the first tests and spec come into being."""
    ws = room_dir(room_id) / "workspaces" / agent
    if ws.exists():
        shutil.rmtree(_writable(ws))
    ws.parent.mkdir(parents=True, exist_ok=True)
    git(".", "clone", "-q", "--no-local", str(original(room_id)), str(ws))
    git(ws, "config", "user.email", f"{agent}@forgeit.local")
    git(ws, "config", "user.name", agent)
    git(ws, "checkout", "-q", "-b", f"agent/{agent}")
    if not bootstrap:
        _ro(ws / "protected")
    return ws


def _walk(p):
    for root, dirs, files in os.walk(p):
        for n in dirs + files:
            yield Path(root) / n


def _ro(p: Path):
    if not p.exists():
        return
    for f in _walk(p):
        f.chmod(f.stat().st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def _writable(p: Path):
    for f in _walk(p):
        try:
            f.chmod(f.stat().st_mode | stat.S_IWUSR)
        except OSError:
            pass
    return p


def commit_workspace(ws: Path, message: str):
    _writable(
        ws / "protected"
    )  # so git can restore state if needed; commit-time check still guards content
    git(ws, "add", "-A")
    git(ws, "commit", "-q", "-m", message, check=False)
    return git(ws, "rev-parse", "HEAD").stdout.strip()


def fetch_branch(room_id, ws: Path, agent) -> str:
    """Bring the agent's committed branch into the original repo (committed files only: clean-checkout rule)."""
    branch = f"agent/{agent}"
    git(original(room_id), "fetch", "-q", str(ws), f"+{branch}:{branch}")
    return branch


def diff_stat(room_id, branch):
    r = git(original(room_id), "diff", "--stat", f"main...{branch}")
    d = git(original(room_id), "diff", f"main...{branch}")
    return {"stat": r.stdout, "diff": d.stdout[:20000]}


def snapshot(room_id) -> str:
    o = original(room_id)
    n = len(git(o, "tag", "--list", "snap-*").stdout.split()) + 1
    tag = f"snap-{n}"
    git(o, "tag", tag, "main")
    return tag


def merge_branches(room_id, branches, message):
    o = original(room_id)
    for b in branches:
        git(o, "merge", "-q", "--no-ff", "-m", f"{message} ({b})", b)


def undo_to(room_id, tag):
    git(original(room_id), "reset", "-q", "--hard", tag)
