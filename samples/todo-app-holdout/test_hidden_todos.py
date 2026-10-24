# Hold-out tests: run only inside the mirror. No agent ever sees these.
def test_done_flag_is_saved(client):
    client.post("/todos", data={"title": "ship"})
    tid = client.get("/api/todos").json()[0]["id"]
    client.post(f"/todos/{tid}/done")
    assert client.get("/api/todos").json()[0]["done"] == 1


def test_marking_an_unknown_todo_is_a_404(client):
    assert client.post("/todos/999/done").status_code == 404
