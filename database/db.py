import os
from datetime import date, timedelta

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from supabase import Client, create_client

load_dotenv()

CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]


def get_db():
    """Open a new Postgres connection with dict-like rows. DDL only (init_db) —
    PostgREST/supabase-py has no CREATE TABLE surface."""
    database_url = os.environ["DATABASE_URL"]
    return psycopg2.connect(database_url, cursor_factory=psycopg2.extras.RealDictCursor)


def get_client() -> Client:
    """Open a Supabase REST client using the service_role key (server-side, RLS bypassed)."""
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_KEY"]
    return create_client(url, key)


def get_auth_client() -> Client:
    """Publishable-keyed client, used ONLY for end-user auth (sign_up /
    sign_in_with_password). Never reuse get_client() for these calls —
    doing so rebinds that client's Authorization header to the signed-in
    user's JWT for all subsequent .table() calls."""
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_PUBLISHABLE_KEY"]
    return create_client(url, key)


def init_db():
    """Create the users and expenses tables if they don't already exist.

    users.id references auth.users(id) — Supabase Auth (not this table) owns
    credentials; this table only holds profile data (name, email)."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id uuid PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            created_at TEXT NOT NULL DEFAULT (now()::text)
        )
    """)
    cursor.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_url TEXT")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id SERIAL PRIMARY KEY,
            user_id uuid NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            description TEXT,
            created_at TEXT NOT NULL DEFAULT (now()::text)
        )
    """)
    conn.commit()
    conn.close()


def ensure_avatars_bucket():
    """Create the public 'avatars' Storage bucket if it doesn't already exist.

    Safe to call on every startup — Storage buckets aren't SQL DDL, so this
    can't go through init_db()/get_db(); it uses the Supabase REST client
    instead, same as everything else besides table creation."""
    supabase = get_client()
    try:
        supabase.storage.create_bucket("avatars", options={"public": True})
    except Exception as e:
        if "already exists" not in str(e).lower():
            raise


def seed_db():
    """Insert demo data for local development. Safe to call on every startup."""
    supabase = get_client()  # service_role — admin.create_user has no session side effect

    existing = supabase.table("users").select("id").limit(1).execute().data
    if existing:
        return

    response = supabase.auth.admin.create_user({
        "email": "demo@spendly.com",
        "password": "demo123",
        "email_confirm": True,
        "user_metadata": {"name": "Demo User"},
    })
    user_id = response.user.id

    supabase.table("users").insert(
        {"id": user_id, "name": "Demo User", "email": "demo@spendly.com"}
    ).execute()

    today = date.today()
    first_of_month = today.replace(day=1)

    def day_offset(n):
        # ISO date n days after the 1st of the current month, clamped so it
        # never lands in the future (important early in the month).
        d = first_of_month + timedelta(days=n)
        return min(d, today).isoformat()

    sample_expenses = [
        {"user_id": user_id, "amount": 850.00, "category": "Food", "date": day_offset(0), "description": "Weekly grocery shopping"},
        {"user_id": user_id, "amount": 350.00, "category": "Transport", "date": day_offset(2), "description": "Uber ride to office"},
        {"user_id": user_id, "amount": 4500.00, "category": "Bills", "date": day_offset(4), "description": "Electricity bill"},
        {"user_id": user_id, "amount": 1200.00, "category": "Health", "date": day_offset(6), "description": "Pharmacy - medicines"},
        {"user_id": user_id, "amount": 900.00, "category": "Entertainment", "date": day_offset(8), "description": "Movie tickets"},
        {"user_id": user_id, "amount": 3200.00, "category": "Shopping", "date": day_offset(10), "description": "New shoes"},
        {"user_id": user_id, "amount": 500.00, "category": "Other", "date": day_offset(12), "description": "Miscellaneous expense"},
        {"user_id": user_id, "amount": 650.00, "category": "Food", "date": day_offset(14), "description": "Dinner with friends"},
    ]

    supabase.table("expenses").insert(sample_expenses).execute()
