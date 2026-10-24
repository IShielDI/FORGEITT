"""Hidden-test authoring workflow (stage 22). Threat model: docs/security/hidden-tests-threat-model.md.

A named teammate writes a hidden test after the first build. It is stored as a draft in the room's
`holdout_drafts/` folder, outside every repo and agent workspace. A second person approves it, and
only then is it copied into `holdout/`, which is mounted into the mirror at verify time. The source
is never served by the API, written to logs or prompts, or shown in the UI: reviewers see the file
name and the test function names only.
"""

import re
import shutil
from pathlib import Path
from typing import Any

from app.core.db import ex, now, q, q1
from app.services.gitops import room_dir

FILENAME_RE = re.compile(r"^test_[A-Za-z0-9_]{1,60}\.py$")
TEST_NAME_RE = re.compile(r"^\s*(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)\s*\(", re.M)
MAX_BYTES = 100_000


class HiddenTestError(ValueError):
    pass


def drafts_dir(room_id: int) -> Path:
    return room_dir(room_id) / "holdout_drafts"


def holdout_dir(room_id: int) -> Path:
    return room_dir(room_id) / "holdout"


def submit(room_id: int, author_id: int | None, filename: str, content: str) -> dict[str, Any]:
    if not FILENAME_RE.match(filename or ""):
        raise HiddenTestError("file name must look like test_something.py")
    if not content.strip() or len(content.encode()) > MAX_BYTES:
        raise HiddenTestError(f"test code must be 1 to {MAX_BYTES} bytes")
    existing = q1("SELECT * FROM hidden_tests WHERE room_id=? AND filename=?", (room_id, filename))
    if existing and existing["status"] == "approved":
        raise HiddenTestError(
            "an approved hidden test already uses that name; retire it or pick another"
        )
    d = drafts_dir(room_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / filename).write_text(content, encoding="utf-8")
    if existing:
        ex(
            "UPDATE hidden_tests SET author_id=?, status='draft', approved_by=NULL, created=? WHERE id=?",
            (author_id, now(), existing["id"]),
        )
    else:
        ex(
            "INSERT INTO hidden_tests(room_id,filename,author_id,status,created) VALUES(?,?,?,'draft',?)",
            (room_id, filename, author_id, now()),
        )
    return describe(room_id, filename)


def approve(
    room_id: int, filename: str, approver_id: int | None, enforce_two_people: bool = True
) -> dict[str, Any]:
    row = q1("SELECT * FROM hidden_tests WHERE room_id=? AND filename=?", (room_id, filename))
    if not row or row["status"] != "draft":
        raise HiddenTestError("there is no draft with that name")
    if enforce_two_people and (approver_id is None or approver_id == row["author_id"]):
        raise HiddenTestError("a second person must approve a hidden test (not its author)")
    h = holdout_dir(room_id)
    h.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(drafts_dir(room_id) / filename, h / filename)
    (drafts_dir(room_id) / filename).unlink(missing_ok=True)
    ex(
        "UPDATE hidden_tests SET status='approved', approved_by=?, approved_at=? WHERE id=?",
        (approver_id, now(), row["id"]),
    )
    return describe(room_id, filename)


def retire(room_id: int, filename: str) -> dict[str, Any]:
    row = q1("SELECT * FROM hidden_tests WHERE room_id=? AND filename=?", (room_id, filename))
    if not row:
        raise HiddenTestError("no hidden test with that name")
    (holdout_dir(room_id) / filename).unlink(missing_ok=True)
    (drafts_dir(room_id) / filename).unlink(missing_ok=True)
    ex("UPDATE hidden_tests SET status='retired' WHERE id=?", (row["id"],))
    return describe(room_id, filename)


def describe(room_id: int, filename: str) -> dict[str, Any]:
    """Metadata for reviewers: who wrote it, who approved it, and the test names. Never the source."""
    row = q1("SELECT * FROM hidden_tests WHERE room_id=? AND filename=?", (room_id, filename)) or {}
    path = (
        holdout_dir(room_id) if row.get("status") == "approved" else drafts_dir(room_id)
    ) / filename
    names = TEST_NAME_RE.findall(path.read_text(encoding="utf-8")) if path.exists() else []
    return {
        "filename": filename,
        "status": row.get("status"),
        "author_id": row.get("author_id"),
        "approved_by": row.get("approved_by"),
        "tests": names,
    }


def listing(room_id: int) -> list[dict[str, Any]]:
    rows = q(
        "SELECT filename FROM hidden_tests WHERE room_id=? AND status!='retired' ORDER BY id",
        (room_id,),
    )
    return [describe(room_id, r["filename"]) for r in rows]
