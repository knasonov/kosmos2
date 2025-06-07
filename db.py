import sqlite3
import os

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "users.db"))


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create tables if they don't exist."""
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            minutes_remaining REAL NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


DEFAULT_USERS = {
    "knasonov": 500,
    "agareev": 100,
    "ismagin": 100,
}


def populate_defaults():
    """Insert the default users if they are missing."""
    conn = get_conn()
    cur = conn.cursor()
    for user, minutes in DEFAULT_USERS.items():
        cur.execute(
            "INSERT OR IGNORE INTO users (username, password, minutes_remaining)"
            " VALUES (?, ?, ?)",
            (user, "kosmos", minutes),
        )
    conn.commit()
    conn.close()


def get_user(username):
    conn = get_conn()
    cur = conn.execute("SELECT * FROM users WHERE username=?", (username,))
    row = cur.fetchone()
    conn.close()
    return row


def set_password(username, password):
    conn = get_conn()
    conn.execute("UPDATE users SET password=? WHERE username=?", (password, username))
    conn.commit()
    conn.close()


def set_limit(username, minutes):
    conn = get_conn()
    conn.execute(
        "UPDATE users SET minutes_remaining=? WHERE username=?",
        (minutes, username),
    )
    conn.commit()
    conn.close()


def add_user(username, password, minutes):
    conn = get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO users (username, password, minutes_remaining)"
        " VALUES (?, ?, ?)",
        (username, password, minutes),
    )
    conn.commit()
    conn.close()


def list_users():
    conn = get_conn()
    rows = conn.execute(
        "SELECT username, minutes_remaining FROM users ORDER BY username"
    ).fetchall()
    conn.close()
    return rows


def deduct_minutes(username, minutes):
    conn = get_conn()
    cur = conn.execute(
        "SELECT minutes_remaining FROM users WHERE username=?", (username,)
    )
    row = cur.fetchone()
    if row is None:
        conn.close()
        return False
    remaining = row["minutes_remaining"]
    if remaining < minutes:
        conn.close()
        return False
    new_remaining = remaining - minutes
    conn.execute(
        "UPDATE users SET minutes_remaining=? WHERE username=?",
        (new_remaining, username),
    )
    conn.commit()
    conn.close()
    return True
