import os
import sqlite3
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

# database/db.py lives in <project_root>/database/, so walking up two levels
# from this file always resolves to the project root, no matter the CWD the
# app was launched from.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "spendly.db")

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


def get_db():
    """Open a new SQLite connection with dict-like rows and foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create the users and expenses tables if they don't already exist."""
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    """)
    conn.commit()
    conn.close()


def seed_db():
    """Insert demo data for local development. Safe to call on every startup."""
    conn = get_db()
    row = conn.execute("SELECT COUNT(*) AS count FROM users").fetchone()
    if row["count"] > 0:
        conn.close()
        return

    password_hash = generate_password_hash("demo123")
    cursor = conn.execute(
        "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
        ("Demo User", "demo@spendly.com", password_hash),
    )
    user_id = cursor.lastrowid

    today = date.today()
    first_of_month = today.replace(day=1)

    def day_offset(n):
        # ISO date n days after the 1st of the current month, clamped so it
        # never lands in the future (important early in the month).
        d = first_of_month + timedelta(days=n)
        return min(d, today).isoformat()

    sample_expenses = [
        (user_id, 850.00, "Food", day_offset(0), "Weekly grocery shopping"),
        (user_id, 350.00, "Transport", day_offset(2), "Uber ride to office"),
        (user_id, 4500.00, "Bills", day_offset(4), "Electricity bill"),
        (user_id, 1200.00, "Health", day_offset(6), "Pharmacy - medicines"),
        (user_id, 900.00, "Entertainment", day_offset(8), "Movie tickets"),
        (user_id, 3200.00, "Shopping", day_offset(10), "New shoes"),
        (user_id, 500.00, "Other", day_offset(12), "Miscellaneous expense"),
        (user_id, 650.00, "Food", day_offset(14), "Dinner with friends"),
    ]

    conn.executemany(
        """
        INSERT INTO expenses (user_id, amount, category, date, description)
        VALUES (?, ?, ?, ?, ?)
        """,
        sample_expenses,
    )
    conn.commit()
    conn.close()
