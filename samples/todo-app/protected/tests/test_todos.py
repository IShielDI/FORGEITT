# Visible tests. Locked: agents may not change these.
def test_health(client):
    assert client.get("/api/health").json() == {"ok": True}


def test_added_todo_is_listed(client):
    r = client.post("/todos", data={"title": "Write spec"}, follow_redirects=False)
    assert r.status_code == 303
    assert [t["title"] for t in client.get("/api/todos").json()] == ["Write spec"]


def test_page_shows_todos_in_order(client):
    for title in ("first", "second"):
        client.post("/todos", data={"title": title})
    page = client.get("/").text
    assert page.index("first") < page.index("second")
