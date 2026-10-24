import os
import shutil
import socket
import stat
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
from defusedxml import ElementTree as ET  # junit.xml is written by agent-controlled code

from app.services.gitops import git, original, room_dir


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def force_rmtree(path: Path):
    """Delete a tree even when git left read-only files behind (Windows refuses to delete those)."""

    def _retry(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except OSError:
            pass

    if path.exists():
        shutil.rmtree(path, onerror=_retry)


class Mirror:
    def __init__(self, room_id, path: Path):
        self.room_id, self.path, self.proc, self.port = room_id, path, None, None
        self.db_path = str(path / "mirror.db")

    def env(self):
        # Agent-written code runs here: pass it a minimal environment, never the platform's keys or secrets.
        keep = {
            k: os.environ[k]
            for k in ("PATH", "LANG", "VIRTUAL_ENV", "SYSTEMROOT")
            if k in os.environ
        }
        return {
            **keep,
            "HOME": str(self.path),
            "DB_PATH": self.db_path,
            "PYTHONPATH": str(self.path),
            "PYTHONDONTWRITEBYTECODE": "1",
        }

    def holdout_dir(self):
        return room_dir(self.room_id) / "holdout"

    def merge_stack(self, queued, new_branch):
        """Original + queued changes + the new change, built from a clean checkout of committed files."""
        git(".", "clone", "-q", "--no-local", str(original(self.room_id)), str(self.path))
        git(self.path, "config", "user.email", "mirror@forgeit.local")
        git(self.path, "config", "user.name", "mirror")
        git(self.path, "checkout", "-q", "-b", "mirror", "main")
        for b in [*queued, new_branch]:
            r = git(
                self.path, "merge", "-q", "--no-ff", "-m", f"mirror {b}", f"origin/{b}", check=False
            )
            if r.returncode:
                git(self.path, "merge", "--abort", check=False)
                return {"ok": False, "conflict_with": b, "detail": (r.stdout + r.stderr)[-500:]}
        self.install_holdout()
        return {"ok": True}

    def install_holdout(self):
        """Hidden hold-out tests live only here, never in any workspace. If the hold-out set brings no fixtures of its own
        (a project started from blank), it borrows the project's own locked fixtures from protected/tests/conftest.py."""
        h = self.holdout_dir()
        if not h.exists() or not any(h.iterdir()):
            return
        shutil.copytree(h, self.path / "_holdout")
        own, locked = (
            self.path / "_holdout" / "conftest.py",
            self.path / "protected/tests/conftest.py",
        )
        if not own.exists() and locked.exists():
            shutil.copy(locked, own)

    def run_tests(self):
        xml = self.path / "junit.xml"
        paths = ["protected/tests"] + (["_holdout"] if (self.path / "_holdout").exists() else [])
        r = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "-c",
                "protected/pytest.ini",
                f"--junitxml={xml}",
                *paths,
            ],
            cwd=self.path,
            env=self.env(),
            capture_output=True,
            text=True,
            timeout=300,
        )
        results = []
        if xml.exists():
            for tc in ET.parse(xml).getroot().iter("testcase"):
                fail = tc.find("failure")
                err = tc.find("error")
                bad = fail if fail is not None else err
                results.append(
                    {
                        "name": f"{tc.get('classname', '').split('.')[-1]}::{tc.get('name')}",
                        "hidden": "_holdout" in (tc.get("classname") or ""),
                        "passed": bad is None,
                        "message": (bad.get("message") or "")[:300] if bad is not None else "",
                    }
                )
        return {"passed": r.returncode == 0, "tests": results, "log": r.stdout[-2000:]}

    def start(self):
        self.port = int(os.environ.get("MIRROR_PORT") or free_port())
        self.proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(self.port),
                "--log-level",
                "warning",
            ],
            cwd=self.path,
            env=self.env(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        for _ in range(60):
            try:
                if (
                    httpx.get(f"http://127.0.0.1:{self.port}/api/health", timeout=1).status_code
                    == 200
                ):
                    return
            except Exception:
                time.sleep(0.25)
        raise RuntimeError("mirror app did not start")

    def orders(self, email):
        import sqlite3

        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        rows = [dict(r) for r in c.execute("SELECT * FROM orders WHERE email=?", (email,))]
        c.close()
        return rows

    def query(self, sql, **params):
        """Read-only ground-truth lookup in the mirror's own database (a human-written check; one SELECT only)."""
        import re
        import sqlite3

        if not re.fullmatch(r"\s*select\b[^;]*;?\s*", sql, re.I):
            raise ValueError("only a single SELECT is allowed")
        c = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in c.execute(sql, params)]
        finally:
            c.close()

    def traces(self):
        import sqlite3

        c = sqlite3.connect(self.db_path)
        c.row_factory = sqlite3.Row
        rows = [
            dict(r)
            for r in c.execute(
                "SELECT method,path,status,handler,db_writes FROM traces ORDER BY id"
            )
        ]
        c.close()
        return rows

    def destroy(self):
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(5)
            except Exception:
                self.proc.kill()
        force_rmtree(self.path)


def new_mirror(room_id) -> Mirror:
    p = room_dir(room_id) / "mirror" / uuid.uuid4().hex[:8]
    p.parent.mkdir(parents=True, exist_ok=True)
    return Mirror(room_id, p)
