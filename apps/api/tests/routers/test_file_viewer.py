"""File viewer: people can browse the project's files and see exactly what a change touched.
It is read-only, reads only from git, and never shows hidden tests."""

from app.core.db import ex, now
from app.services import gitops


def _commit_change(room, files: dict[str, str]) -> int:
    """Commit on a side branch of the room's repo, as an agent's change would, and record it."""
    repo = gitops.original(room)
    gitops.git(repo, "checkout", "-q", "-b", f"agent/test-{now()}")
    for path, text in files.items():
        p = repo / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    gitops.git(repo, "add", "-A")
    gitops.git(repo, "commit", "-q", "-m", "test change")
    sha = gitops.git(repo, "rev-parse", "HEAD").stdout.strip()
    gitops.git(repo, "checkout", "-q", "main")
    return ex(
        "INSERT INTO changes(room_id,agent,branch,summary,status,created,commit_sha) "
        "VALUES(?,?,?,?,?,?,?)",
        (room, "riya-agent", "agent/test", "test", "ready", now(), sha),
    )


def test_list_and_read_the_project_files(api, room):
    files = api.get(f"/api/rooms/{room}/files").json()
    assert "app/main.py" in files and not any(f.startswith("holdout") for f in files)

    body = api.get(f"/api/rooms/{room}/files/content", params={"path": "app/main.py"}).json()
    assert body["binary"] is False and "def " in body["text"]


def test_unknown_paths_and_versions_are_refused(api, room):
    for params in (
        {"path": "../../etc/passwd"},
        {"path": "app/nope.py"},
        {"path": "app/main.py", "ref": "HEAD~1"},
        {"path": "app/main.py", "ref": "--output=x"},
    ):
        assert api.get(f"/api/rooms/{room}/files/content", params=params).status_code == 404


def test_a_change_shows_the_files_it_touched_and_their_diff(api, room):
    cid = _commit_change(room, {"app/notes.py": "NOTE = 1\n"})

    r = api.get(f"/api/changes/{cid}/files").json()
    assert {"status": "A", "path": "app/notes.py"} in r["files"]

    d = api.get(f"/api/changes/{cid}/files/diff", params={"path": "app/notes.py"}).json()
    assert "+NOTE = 1" in d["diff"]

    content = api.get(
        f"/api/rooms/{room}/files/content", params={"path": "app/notes.py", "ref": r["commit"]}
    ).json()
    assert content["text"] == "NOTE = 1\n"
    assert (
        api.get(f"/api/changes/{cid}/files/diff", params={"path": "app/main.py"}).status_code == 404
    )


def test_hidden_tests_never_show_even_if_committed_by_mistake(api, room):
    cid = _commit_change(room, {"holdout/test_secret.py": "SECRET = 1\n", "app/ok.py": "OK = 1\n"})
    sha = api.get(f"/api/changes/{cid}/files").json()["commit"]

    listed = [f["path"] for f in api.get(f"/api/changes/{cid}/files").json()["files"]]
    assert listed == ["app/ok.py"]
    assert (
        "holdout/test_secret.py"
        not in api.get(f"/api/rooms/{room}/files", params={"ref": sha}).json()
    )
    r = api.get(
        f"/api/rooms/{room}/files/content", params={"path": "holdout/test_secret.py", "ref": sha}
    )
    assert r.status_code == 404
