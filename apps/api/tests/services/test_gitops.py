"""Stage 12: managed repos with a protected main (temp repos via the room fixture)."""

import pytest

from app.services import gitops


def _branch_with_commit(room, name, filename="app/new.py"):
    o = gitops.original(room)
    gitops.git(o, "checkout", "-q", "-b", name, "main")
    (o / filename).write_text("x = 1\n")
    gitops.git(o, "add", "-A")
    gitops.git(o, "commit", "-q", "-m", name)
    gitops.git(o, "checkout", "-q", "main")
    return gitops.git(o, "rev-parse", name).stdout.strip()


def test_direct_main_update_is_refused(api, room):
    sha = _branch_with_commit(room, "feature")
    o = gitops.original(room)

    r = gitops.git(o, "update-ref", "refs/heads/main", sha, check=False)

    assert r.returncode != 0 and "protected" in r.stderr
    assert gitops.git(o, "rev-parse", "main").stdout.strip() != sha


def test_push_to_main_from_a_clone_is_refused(api, room, tmp_path):
    clone = tmp_path / "clone"
    gitops.git(".", "clone", "-q", "--no-local", str(gitops.original(room)), str(clone))
    gitops.git(clone, "config", "user.email", "agent@x")
    gitops.git(clone, "config", "user.name", "agent")
    (clone / "app/hack.py").write_text("x = 2\n")
    gitops.git(clone, "add", "-A")
    gitops.git(clone, "commit", "-q", "-m", "sneaky")

    r = gitops.git(clone, "push", "-q", "origin", "HEAD:main", check=False)

    assert r.returncode != 0


def test_merge_service_can_update_main_and_tag_a_release(api, room):
    sha = _branch_with_commit(room, "feature")

    merged = gitops.merge_branches(room, ["feature"], "Approved by riya")
    tag = gitops.tag_release(room)

    o = gitops.original(room)
    assert gitops.git(o, "merge-base", "--is-ancestor", sha, "main", check=False).returncode == 0
    assert tag == "release/1" and gitops.git(o, "rev-parse", tag).stdout.strip() == merged


def test_merge_conflict_is_detected(api, room):
    _branch_with_commit(room, "a1", "app/db.py")
    o = gitops.original(room)
    gitops.git(o, "checkout", "-q", "-b", "a2", "main")
    (o / "app/db.py").write_text("A = 2\n")
    gitops.git(o, "commit", "-q", "-am", "a2")
    gitops.git(o, "checkout", "-q", "main")
    gitops.merge_branches(room, ["a1"], "m")

    with pytest.raises(RuntimeError):
        gitops.merge_branches(room, ["a2"], "m")
    gitops.git(o, "merge", "--abort", check=False)


@pytest.mark.parametrize("name", ["-x", "--upload-pack=evil", "a..b", "a b", "", "x/"])
def test_unsafe_branch_names_are_rejected(name):
    with pytest.raises(ValueError):
        gitops.safe_branch(name)


def test_undo_restores_the_snapshot(api, room):
    before = gitops.git(gitops.original(room), "rev-parse", "main").stdout.strip()
    snap = gitops.snapshot(room)
    _branch_with_commit(room, "feature")
    gitops.merge_branches(room, ["feature"], "m")

    gitops.undo_to(room, snap)

    assert gitops.git(gitops.original(room), "rev-parse", "main").stdout.strip() == before
