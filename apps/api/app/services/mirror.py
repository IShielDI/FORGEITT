"""The mirror: a throwaway candidate build (main + queued changes + the new change).

Candidate code runs either in a fresh `forgeit-mirror` container (tests with no network, no keys,
capabilities dropped, resource limits) or, when Docker or the image is missing, on the host with a
minimal environment. The mode is recorded with every result so nobody mistakes host runs for isolated
ones. The app's database and traces are read by the platform from the mirror folder.
"""

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

from app.core import config
from app.services.gitops import git, original, room_dir

CONTAINER_PORT = 8000
TEST_TIMEOUT_S = 300
_image_ok: dict[str, bool] = {}


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


def _docker_image_ready(image: str) -> bool:
    if image not in _image_ok:
        try:
            _image_ok[image] = bool(shutil.which("docker")) and (
                subprocess.run(
                    ["docker", "image", "inspect", image], capture_output=True, timeout=20
                ).returncode
                == 0
            )
        except Exception:
            _image_ok[image] = False
    return _image_ok[image]


def isolation_mode() -> str:
    if config.MIRROR_SANDBOX in ("docker", "host"):
        return config.MIRROR_SANDBOX
    return "docker" if _docker_image_ready(config.MIRROR_IMAGE) else "host"


def _container_user() -> str:
    getuid, getgid = getattr(os, "getuid", None), getattr(os, "getgid", None)
    return f"{getuid()}:{getgid()}" if getuid and getgid else "1000:1000"


class Mirror:
    def __init__(self, room_id, path: Path):
        self.room_id, self.path, self.proc, self.port = room_id, path, None, None
        self.db_path = str(path / "mirror.db")
        self.isolation = isolation_mode()
        self.container = None

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

    def docker_args(self, argv, network="none", detach=False, publish=None, name=None):
        """A fresh container with only this mirror folder mounted and no keys in its environment."""
        a = ["docker", "run", "--rm"]
        if detach:
            a += ["-d"]
        if name:
            a += ["--name", name]
        a += [
            "--network",
            network,
            "--user",
            _container_user(),
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "256",
            "--memory",
            "1g",
            "--cpus",
            "1",
            "-v",
            f"{self.path}:/work",
            "-w",
            "/work",
            "-e",
            "HOME=/work",
            "-e",
            "DB_PATH=/work/mirror.db",
            "-e",
            "PYTHONPATH=/work",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
        ]
        if publish:
            a += ["-p", publish]
        return [*a, config.MIRROR_IMAGE, *argv]

    def exec(self, argv, timeout=TEST_TIMEOUT_S):
        """Run one command against the candidate. Returns (exit_code, output, duration_ms)."""
        t0 = time.monotonic()
        if self.isolation == "docker":
            cmd, cwd, env = self.docker_args(argv), None, None
        else:
            cmd, cwd, env = (
                [sys.executable if argv[0] == "python" else argv[0], *argv[1:]],
                self.path,
                self.env(),
            )
        try:
            r = subprocess.run(
                cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout
            )
            code, out = r.returncode, (r.stdout + r.stderr)
        except subprocess.TimeoutExpired:
            code, out = 124, f"timed out after {timeout}s"
        return code, out[-20000:], int((time.monotonic() - t0) * 1000)

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

    def run_suite(self, label, paths):
        """One pytest run (its own exit code and junit report). Hidden test sources never leave here."""
        xml = f"junit-{label}.xml"
        code, out, ms = self.exec(
            [
                "python",
                "-m",
                "pytest",
                "-q",
                "-p",
                "no:cacheprovider",
                "-c",
                "protected/pytest.ini",
                f"--junitxml={xml}",
                *paths,
            ]
        )
        results = []
        if (self.path / xml).exists():
            for tc in ET.parse(self.path / xml).getroot().iter("testcase"):
                bad = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
                results.append(
                    {
                        "name": f"{tc.get('classname', '').split('.')[-1]}::{tc.get('name')}",
                        "hidden": label == "hidden" or "_holdout" in (tc.get("classname") or ""),
                        "passed": bad is None,
                        "message": (bad.get("message") or "")[:300] if bad is not None else "",
                    }
                )
        return {"exit_code": code, "tests": results, "log": out, "duration_ms": ms}

    def run_tests(self):
        """Locked tests, then hidden tests: separate runs so each has its own exit code."""
        locked = self.run_suite("locked", ["protected/tests"])
        runs = [locked]
        if (self.path / "_holdout").exists():
            runs.append(self.run_suite("hidden", ["_holdout"]))
        return {
            "passed": all(r["exit_code"] == 0 for r in runs),
            "tests": [t for r in runs for t in r["tests"]],
            "log": locked["log"][-2000:],
            "isolation": self.isolation,
            # exit codes and durations per suite; the hidden suite's raw output is never kept
            "suites": {
                label: {"exit_code": r["exit_code"], "duration_ms": r["duration_ms"]}
                for label, r in zip(("locked", "hidden"), runs, strict=False)
            },
        }

    def start(self):
        self.port = int(os.environ.get("MIRROR_PORT") or free_port())
        if self.isolation == "docker":
            self.container = f"forgeit-mirror-{uuid.uuid4().hex[:10]}"
            argv = [
                "python",
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(CONTAINER_PORT),
                "--log-level",
                "warning",
            ]
            subprocess.run(
                self.docker_args(
                    argv,
                    network="bridge",
                    detach=True,
                    publish=f"127.0.0.1:{self.port}:{CONTAINER_PORT}",
                    name=self.container,
                ),
                capture_output=True,
                check=True,
                timeout=60,
            )
        else:
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
        for _ in range(120):
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
        if self.container:
            subprocess.run(["docker", "rm", "-f", self.container], capture_output=True, timeout=60)
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
