import os
import sqlite3


def db_path():
    return os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "todo.db"))


def conn():
    c = sqlite3.connect(db_path())
    c.row_factory = sqlite3.Row
    return c


def init():
    c = conn()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS todos(id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT NOT NULL, done INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS traces(id INTEGER PRIMARY KEY AUTOINCREMENT, method TEXT, path TEXT, status INTEGER, handler TEXT, db_writes INTEGER);
        """
    )
    c.commit()
    c.close()
