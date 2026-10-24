"""Managed git repos per workspace: the protected original (main), per-task clones, snapshots, undo.

Only the Merge Service may move `main`: a `reference-transaction` hook in every original rejects any
update of refs/heads/main (local or pushed from a clone) unless FORGEIT_MERGE_SERVICE=1 is set by
`merge_branches`/`undo_to`. Git is always called with an argument list, never through a shell.
"""

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

from app.core.config import DATA, SAMPLE

MERGE_ENV = "FORGEIT_MERGE_SERVICE"
BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,199}$")
GUARD_HOOK = """#!/bin/sh
# ForgeIt: main is protected. Only the Merge Service (after a recorded human approval) may update it.
[ "$1" = "prepared" ] || exit 0
[ "$FORGEIT_MERGE_SERVICE" = "1" ] && exit 0
while read -r old new ref; do
  if [ "$ref" = "refs/heads/main" ]; then
    echo "ForgeIt: refs/heads/main is protected; only the merge service may update it" >&2
    exit 1
  fi
done
exit 0
"""


def git(cwd, *args, check=True, merge_service=False):
    env = (
        {**os.environ, MERGE_ENV: "1"}
        if merge_service
        else {k: v for k, v in os.environ.items() if k != MERGE_ENV}
    )
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, env=env)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip() or r.stdout.strip()}")
    return r


def safe_branch(name: str) -> str:
    """Reject branch names that could be read as options or escape refs/heads."""
    if not BRANCH_RE.match(name or "") or ".." in name or name.endswith((".lock", "/")):
        raise ValueError(f"unsafe branch name: {name!r}")
    return name


def install_guard(repo: Path) -> None:
    hook = repo / ".git" / "hooks" / "reference-transaction"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_bytes(GUARD_HOOK.encode("utf-8"))  # LF endings so sh can run it on Windows too
    hook.chmod(0o755)


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
    install_guard(o)
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
    install_guard(o)
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
    """The Merge Service: the only code path allowed to move main."""
    o = original(room_id)
    install_guard(o)  # rooms created before the guard existed get it now
    for b in branches:
        git(
            o,
            "merge",
            "-q",
            "--no-ff",
            "-m",
            f"{message} ({b})",
            safe_branch(b),
            merge_service=True,
        )
    return git(o, "rev-parse", "main").stdout.strip()


def tag_release(room_id) -> str:
    """Tag the merged main as release/<n> (rollback points)."""
    o = original(room_id)
    n = len(git(o, "tag", "--list", "release/*").stdout.split()) + 1
    tag = f"release/{n}"
    git(o, "tag", tag, "main")
    return tag


def head(room_id, branch) -> str:
    return git(original(room_id), "rev-parse", safe_branch(branch)).stdout.strip()


def undo_to(room_id, tag):
    git(original(room_id), "reset", "-q", "--hard", safe_branch(tag), merge_service=True)


# ---- read-only file viewer (for people, never agents) ----------------------------------------
# Hidden tests live outside this repo (holdout/ and holdout_drafts/ beside it), so a git ref can
# never reach them; the prefixes below are a second guard in case one is ever committed by mistake.
VIEW_HIDDEN = ("holdout/", "holdout_drafts/", ".git/")
VIEW_MAX_BYTES = 200_000
REF_RE = re.compile(r"^(main|[0-9a-f]{40})$")


def _view_ref(ref: str) -> str:
    if not REF_RE.match(ref or ""):
        raise ValueError("unknown version")
    return ref


def _viewable(path: str) -> bool:
    return not path.startswith(VIEW_HIDDEN) and "/holdout/" not in path


def list_files(room_id, ref="main") -> list[str]:
    r = git(original(room_id), "ls-tree", "-r", "--name-only", _view_ref(ref))
    return [p for p in r.stdout.splitlines() if p and _viewable(p)]


def read_file(room_id, ref, path) -> dict:
    """One file's text at a version. Only paths that exist in that version can be read."""
    if path not in list_files(room_id, ref):
        raise FileNotFoundError(path)
    data = subprocess.run(
        ["git", "show", f"{_view_ref(ref)}:{path}"], cwd=original(room_id), capture_output=True
    ).stdout
    binary = b"\0" in data[:8000]
    text = None if binary else data[:VIEW_MAX_BYTES].decode("utf-8", "replace")
    return {
        "path": path,
        "size": len(data),
        "binary": binary,
        "truncated": len(data) > VIEW_MAX_BYTES,
        "text": text,
    }


def changed_files(room_id, sha) -> list[dict]:
    """What one change's commit added (A), modified (M) or deleted (D), against its parent."""
    r = git(original(room_id), "diff", "--name-status", f"{_view_ref(sha)}^", sha, check=False)
    out = []
    for line in r.stdout.splitlines():
        status, _, path = line.partition("\t")
        if path and _viewable(path):
            out.append({"status": status[:1], "path": path})
    return out


def file_diff(room_id, sha, path) -> str:
    if path not in {f["path"] for f in changed_files(room_id, sha)}:
        raise FileNotFoundError(path)
    return git(original(room_id), "diff", f"{_view_ref(sha)}^", sha, "--", path).stdout[
        :VIEW_MAX_BYTES
    ]
