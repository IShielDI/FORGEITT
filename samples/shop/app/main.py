from fastapi import FastAPI, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from . import db

app = FastAPI(title="Tiny Shop")
db.init()

PAGE = """<!doctype html><html><head><meta charset=utf-8><title>Tiny Shop</title></head>
<body><nav><a href="/products">Products</a> | <a href="/cart">Cart</a></nav>{body}</body></html>"""

def page(body): return HTMLResponse(PAGE.format(body=body))
def money(c): return f"${c/100:.2f}"
def who(request): return request.cookies.get("uid")

@app.middleware("http")
async def trace(request: Request, call_next):
    db.reset_writes()
    resp = await call_next(request)
    route = request.scope.get("route")
    handler = getattr(route, "name", "") if route else ""
    if not request.url.path.startswith("/api/"):
        c = db.conn()
        c.execute("INSERT INTO traces(method,path,status,handler,db_writes) VALUES(?,?,?,?,?)",
                  (request.method, request.url.path, resp.status_code, handler, db.writes()))
        c.commit(); c.close()
    return resp

@app.get("/")
def home(): return page("<h1>Tiny Shop</h1><p><a href='/signup'>Sign up</a> to start shopping.</p>")

@app.get("/signup")
def signup_form():
    return page("""<h1>Sign up</h1><form method="post" action="/signup">
    <label>Email <input name="email" type="email" required></label>
    <label>Password <input name="password" type="password" required></label>
    <button type="submit">Create account</button></form>""")

@app.post("/signup")
def signup(email: str = Form(...), password: str = Form(...)):
    c = db.conn()
    if c.execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
        c.close(); return page("<p>Account already exists.</p>")
    db.write(c, "INSERT INTO users(email,password) VALUES(?,?)", (email, password))
    c.commit(); c.close()
    r = RedirectResponse("/products", status_code=303)
    r.set_cookie("uid", email)
    return r

@app.get("/products")
def products():
    c = db.conn()
    rows = c.execute("SELECT * FROM products").fetchall(); c.close()
    items = "".join(
        f"<li>{r['name']} - {money(r['price_cents'])}"
        f"<form method='post' action='/cart/add'><input type='hidden' name='product_id' value='{r['id']}'>"
        f"<label>Quantity <input name='qty' type='number' value='1' min='1'></label>"
        f"<button type='submit'>Add {r['name']} to cart</button></form></li>" for r in rows)
    return page(f"<h1>Products</h1><ul>{items}</ul>")

@app.post("/cart/add")
def cart_add(request: Request, product_id: int = Form(...), qty: int = Form(1)):
    email = who(request)
    if not email: return RedirectResponse("/signup", status_code=303)
    c = db.conn()
    db.write(c, "INSERT INTO cart_items(email,product_id,qty) VALUES(?,?,?)", (email, product_id, qty))
    c.commit(); c.close()
    return RedirectResponse("/cart", status_code=303)

def cart_lines(c, email):
    return c.execute("""SELECT p.id pid, p.name, p.price_cents, SUM(ci.qty) qty
        FROM cart_items ci JOIN products p ON p.id=ci.product_id
        WHERE ci.email=? GROUP BY p.id""", (email,)).fetchall()

@app.get("/cart")
def cart(request: Request):
    email = who(request)
    if not email: return RedirectResponse("/signup", status_code=303)
    c = db.conn(); lines = cart_lines(c, email); c.close()
    total = sum(l["price_cents"] * l["qty"] for l in lines)
    rows = "".join(f"<li>{l['name']} x {l['qty']} = {money(l['price_cents']*l['qty'])}</li>" for l in lines)
    return page(f"<h1>Your cart</h1><ul>{rows}</ul><p>Cart total: {money(total)}</p>"
                "<form method='post' action='/checkout'><button type='submit'>Check out</button></form>")

@app.post("/checkout")
def checkout(request: Request):
    email = who(request)
    if not email: return RedirectResponse("/signup", status_code=303)
    c = db.conn(); lines = cart_lines(c, email)
    if not lines:
        c.close(); return page("<p>Your cart is empty.</p>")
    total = sum(l["price_cents"] * l["qty"] for l in lines)
    cur = db.write(c, "INSERT INTO orders(email,total_cents) VALUES(?,?)", (email, total))
    oid = cur.lastrowid
    for l in lines:
        db.write(c, "INSERT INTO order_items(order_id,product_id,qty,price_cents) VALUES(?,?,?,?)",
                 (oid, l["pid"], l["qty"], l["price_cents"]))
    db.write(c, "DELETE FROM cart_items WHERE email=?", (email,))
    c.commit(); c.close()
    return page(f"<h1>Order placed</h1><p>Confirmation number: ORD-{oid}</p><p>Order total: {money(total)}</p>")

@app.get("/api/orders")
def api_orders(email: str):
    c = db.conn()
    rows = [dict(r) for r in c.execute("SELECT * FROM orders WHERE email=?", (email,))]
    c.close(); return JSONResponse(rows)

@app.get("/api/traces")
def api_traces():
    c = db.conn()
    rows = [dict(r) for r in c.execute("SELECT * FROM traces ORDER BY id")]
    c.close(); return JSONResponse(rows)

@app.get("/api/health")
def health(): return {"ok": True}
