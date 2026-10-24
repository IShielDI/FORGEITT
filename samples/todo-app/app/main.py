from html import escape

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from . import db

app = FastAPI(title="Todo App")
db.init()


@app.middleware("http")
async def trace(request: Request, call_next):
    resp = await call_next(request)
    route = request.scope.get("route")
    if not request.url.path.startswith("/api/"):
        c = db.conn()
        c.execute(
            "INSERT INTO traces(method,path,status,handler,db_writes) VALUES(?,?,?,?,0)",
            (request.method, request.url.path, resp.status_code, getattr(route, "name", "") if route else ""),
        )
        c.commit()
        c.close()
    return resp


def list_todos():
    c = db.conn()
    rows = [dict(r) for r in c.execute("SELECT id, title, done FROM todos ORDER BY id")]
    c.close()
    return rows


@app.get("/")
def home():
    items = "".join(
        f"<li>{'[x]' if t['done'] else '[ ]'} {escape(t['title'])}"
        f"<form method='post' action='/todos/{t['id']}/done'><button type='submit'>Done</button></form></li>"
        for t in list_todos()
    )
    return HTMLResponse(
        "<!doctype html><title>Todos</title><h1>Todos</h1>"
        "<form method='post' action='/todos'><input name='title' required><button type='submit'>Add</button></form>"
        f"<ul>{items}</ul>"
    )


@app.post("/todos")
def add(title: str = Form(...)):
    c = db.conn()
    c.execute("INSERT INTO todos(title) VALUES(?)", (title.strip(),))
    c.commit()
    c.close()
    return RedirectResponse("/", status_code=303)


@app.post("/todos/{todo_id}/done")
def done(todo_id: int):
    c = db.conn()
    cur = c.execute("UPDATE todos SET done=1 WHERE id=?", (todo_id,))
    c.commit()
    c.close()
    if cur.rowcount == 0:
        raise HTTPException(404, "no such todo")
    return RedirectResponse("/", status_code=303)


@app.get("/api/todos")
def api_todos():
    return JSONResponse(list_todos())


@app.get("/api/health")
def health():
    return {"ok": True}
