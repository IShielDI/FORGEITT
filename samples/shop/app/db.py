import os, sqlite3, contextvars

_writes = contextvars.ContextVar("writes", default=0)

def db_path():
    return os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "shop.db"))

def conn():
    c = sqlite3.connect(db_path())
    c.row_factory = sqlite3.Row
    return c

def write(c, sql, args=()):
    """All data changes go through here so the trace can count DB writes."""
    _writes.set(_writes.get() + 1)
    return c.execute(sql, args)

def reset_writes():
    _writes.set(0)

def writes():
    return _writes.get()

def init():
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(email TEXT PRIMARY KEY, password TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS products(id INTEGER PRIMARY KEY, name TEXT NOT NULL, price_cents INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS cart_items(email TEXT, product_id INTEGER, qty INTEGER);
    CREATE TABLE IF NOT EXISTS orders(id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT, total_cents INTEGER);
    CREATE TABLE IF NOT EXISTS order_items(order_id INTEGER, product_id INTEGER, qty INTEGER, price_cents INTEGER);
    CREATE TABLE IF NOT EXISTS traces(id INTEGER PRIMARY KEY AUTOINCREMENT, method TEXT, path TEXT, status INTEGER, handler TEXT, db_writes INTEGER);
    """)
    if not c.execute("SELECT 1 FROM products").fetchone():
        c.executemany("INSERT INTO products(id,name,price_cents) VALUES(?,?,?)",
                      [(1, "Notebook", 1200), (2, "Pen", 350), (3, "Mug", 899)])
    c.commit(); c.close()
