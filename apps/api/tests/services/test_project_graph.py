"""Project memory graph, relevant files per task, and the optional edit scope."""

from app.core.db import ex
from app.services import agent_runner, context, knowledge, orchestrator, planner
from tests.support.planning import proposed_plan
from tests.support.scripted import ScriptedProvider

E = "str_replace_based_edit_tool"


def _approved(room):
    proposed_plan(room)
    planner.approve(room)
    return {t["key"]: t["id"] for t in planner.tasks(room)}


def _run(room, task_id, path, text="X = 1\n"):
    plan = ScriptedProvider(
        [[("tool", E, {"command": "create", "path": path, "file_text": text})], [("text", "done")]]
    )
    r = agent_runner.run_task(
        room, "riya-agent", f"edit {path}", provider=plan, summary=f"edit {path}", task_id=task_id
    )
    return orchestrator.submit_change(room, r["change_id"])


def test_graph_has_parts_files_tasks_and_their_links(api, room):
    tasks = _approved(room)
    g = knowledge.project_graph(room)
    ids = {n["id"]: n for n in g["nodes"]}
    rel = {(e["source"], e["relation"], e["target"]) for e in g["edges"]}

    assert ids["part:database"]["type"] == "part" and ids["file:app/db.py"]["type"] == "file"
    assert ("part:database", "owns", "file:app/db.py") in rel
    assert (f"task:{tasks['db']}", "works_on", "part:database") in rel
    assert any(
        e["relation"] == "implemented_by" and e["target"] == f"task:{tasks['ui']}"
        for e in g["edges"]
    )


def test_changes_link_the_files_they_touched(api, room):
    tasks = _approved(room)
    ch = _run(room, tasks["db"], "app/db.py", "A = 1\n")

    rel = {
        (e["source"], e["relation"], e["target"]) for e in knowledge.project_graph(room)["edges"]
    }
    assert (f"change:{ch['id']}", "touched", "file:app/db.py") in rel


def test_relevant_files_cover_own_part_and_what_dependencies_changed(api, room):
    tasks = _approved(room)
    _run(
        room, tasks["db"], "app/schema_notes.py"
    )  # the db task (a dependency of api) touched a new file
    files = {f["path"]: f["why"] for f in knowledge.relevant_files(room, tasks["api"])}

    assert files["app/main.py"] == "part 'backend'"
    assert "dependency 'db'" in files["app/schema_notes.py"]
    assert "app/db.py" not in files  # the database part's own file is not the api task's business


def test_context_pack_lists_relevant_files_first(api, room):
    tasks = _approved(room)
    pack = context.build(tasks["api"])

    assert pack["items"][0]["cite"] == "file:app/main.py"
    assert "Relevant files (start here" in pack["markdown"]


def test_edit_scope_rejects_changes_outside_the_tasks_files(api, room):
    tasks = _approved(room)
    ex("UPDATE rooms SET edit_scope='task' WHERE id=?", (room,))

    outside = _run(room, tasks["db"], "app/unrelated.py")
    inside = _run(room, tasks["db"], "app/db.py", "B = 2\n")

    assert outside["status"] == "rejected_scope"
    assert inside["status"] not in ("rejected_scope", "rejected_firewall")


def test_edit_scope_off_allows_any_file(api, room):
    tasks = _approved(room)
    assert _run(room, tasks["db"], "app/unrelated.py")["status"] != "rejected_scope"


def test_in_scope_matches_files_and_folders():
    assert knowledge.in_scope("app/db.py", ["app/db.py"])
    assert knowledge.in_scope("app/x/y.py", ["app/"])
    assert not knowledge.in_scope("app/dbx.py", ["app/db.py"])


def test_graph_and_scope_endpoints(api, room):
    tasks = _approved(room)
    assert api.get(f"/api/rooms/{room}/graph").json()["nodes"]
    assert api.get(f"/api/tasks/{tasks['db']}/files").json()[0]["path"] == "app/db.py"
    assert api.put(f"/api/rooms/{room}/edit-scope", json={"scope": "files"}).status_code == 400
    assert api.put(f"/api/rooms/{room}/edit-scope", json={"scope": "task"}).json() == {
        "scope": "task"
    }
