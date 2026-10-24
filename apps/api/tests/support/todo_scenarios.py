"""Scripted agents for the todo-app demo (tests only). One of them plants a bug the hidden tests catch."""

from tests.support.scripted import ScriptedProvider

E = "str_replace_based_edit_tool"
QUERY = 'rows = [dict(r) for r in c.execute("SELECT id, title, done FROM todos ORDER BY id")]'
BROKEN = 'rows = [dict(r) for r in c.execute("SELECT id, title, 0 AS done FROM todos ORDER BY id")]  # faster'


def ui_heading():
    return ScriptedProvider(
        [
            [("tool", E, {"command": "view", "path": "TASK_CONTEXT.md"})],
            [
                (
                    "tool",
                    E,
                    {
                        "command": "str_replace",
                        "path": "app/main.py",
                        "old_str": "<h1>Todos</h1>",
                        "new_str": "<h1>Team todos</h1>",
                    },
                )
            ],
            [("text", "Handoff: renamed the page heading to Team todos.")],
        ]
    )


def api_speedup_with_bug():
    return ScriptedProvider(
        [
            [
                (
                    "tool",
                    E,
                    {
                        "command": "str_replace",
                        "path": "app/main.py",
                        "old_str": QUERY,
                        "new_str": BROKEN,
                    },
                )
            ],
            [("text", "Handoff: made the todo listing faster. Visible tests pass.")],
        ]
    )


def api_fix():
    return ScriptedProvider(
        [
            [
                (
                    "tool",
                    E,
                    {
                        "command": "str_replace",
                        "path": "app/main.py",
                        "old_str": QUERY,
                        "new_str": QUERY + "  # done flag comes from the table",
                    },
                )
            ],
            [("text", "Handoff: the listing reads the real done flag again.")],
        ]
    )
