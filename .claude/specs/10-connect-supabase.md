# Spec: Connect Supabase

## Overview

Spendly currently persists data to a local SQLite file (`spendly.db`), which
is gitignored and lives only on disk wherever the app happens to run. Now
that the app is being prepared for deployment (see the Procfile and dynamic
`PORT` binding added just before this step), a local SQLite file is no
longer viable — most hosting platforms use ephemeral or read-only
filesystems, so the database would reset on every redeploy or restart. This
step replaces the SQLite datastore with a hosted Supabase Postgres database.
The goal is durable, shared storage in production while keeping local dev
friction low via a `.env` file holding the connection details.

**Superseded:** this spec originally called for a direct `psycopg2`
connection with no ORM/query-builder client, on the reasoning that raw SQL
keeps parity with the existing `sqlite3` style. The user explicitly chose
instead to use Supabase's official Python client (`supabase-py`) for all
data access, overriding that rule for this integration specifically. The
implementation is a hybrid: `supabase-py`'s `.table(...)` query builder is
used for all reads/writes (`seed_db()` and every route in `app.py`), while
a raw `psycopg2` connection is kept **only** inside `init_db()`, because
Supabase's REST API (what `supabase-py` talks to) cannot execute DDL
(`CREATE TABLE`) at all — there is no query-builder equivalent for schema
creation.

## Depends on

- Step 01 (Database Setup) — this step replaces that step's SQLite
  implementation of `database/db.py`, not its schema design.
- Implicitly depends on every route added since (registration, login,
  profile, add/edit/delete expense) because their SQL is being ported from
  SQLite to Postgres syntax in the same pass.

## Routes

No new routes.

## Database changes

Same two tables (`users`, `expenses`), same columns, re-expressed in
Postgres syntax and created against the Supabase database instead of a
local `.db` file:

- `users.id`: `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`
- `expenses.id`: `INTEGER PRIMARY KEY AUTOINCREMENT` → `SERIAL PRIMARY KEY`
- `created_at` / `date` columns: keep as `TEXT` with the same
  `datetime('now')`-style default expressed as Postgres's
  `DEFAULT (now()::text)`, so existing string-based date parsing
  (`datetime.strptime(row["created_at"][:10], ...)`) in `app.py` keeps
  working unchanged.
- `expenses.user_id` foreign key to `users.id`: same relationship, standard
  Postgres `REFERENCES` syntax.
- All `CREATE TABLE` statements stay `CREATE TABLE IF NOT EXISTS` — no
  migration framework introduced.

## Templates

- **Create:** none
- **Modify:** none — this is a backend-only change, no template touches
  the database layer directly.

## Files to change

- `database/db.py` — keep `get_db()` (raw `psycopg2` + `RealDictCursor`,
  `DATABASE_URL`) but scope it to DDL only, used solely by `init_db()`.
  Add `get_client()`, returning a `supabase-py` `Client` built from
  `SUPABASE_URL`/`SUPABASE_KEY` (service_role secret). Rewrite `seed_db()`
  to use `get_client()`'s `.table(...)` query builder instead of raw SQL
  (bulk `.insert()` of a list of dicts in place of `executemany`).
- `app.py` — replace every raw SQL call (`conn.cursor()` +
  `cursor.execute(...)`) with the `supabase-py` query builder
  (`get_client().table(...).select()/.insert()/.update()/.delete()`)
  across all routes and helpers (`register`, `login`, `profile` helpers,
  `add_expense`, `edit_expense`, `delete_expense`). The
  `_date_filter_clause` raw-WHERE-string helper is replaced by
  `_apply_date_filter`, which chains `.gte()`/`.lte()` onto a query
  object. Aggregation (`SUM`, `GROUP BY`, previously done in SQL) is done
  client-side in Python after fetching matching rows, since PostgREST's
  aggregate functions require a non-default per-project Postgres role
  setting. The `sqlite3.IntegrityError`/`psycopg2.errors.UniqueViolation`
  catch in `register` becomes `postgrest.APIError` with `e.code ==
  "23505"`.
- `requirements.txt` — add `psycopg2-binary`, `python-dotenv`, and
  `supabase`.
- `.gitignore` — already ignores `.env`; also remove the now-stale
  `spendly.db` entry once SQLite is fully retired (optional cleanup, not
  required for functionality).

## Files to create

- `.env.example` — documents `DATABASE_URL` (pooler connection, for
  `init_db()`'s DDL) and `SUPABASE_URL`/`SUPABASE_KEY` (service_role
  secret, for `get_client()`), with placeholder values so contributors
  know what to put in their own untracked `.env`.

## New dependencies

- `psycopg2-binary` — Postgres driver, used only by `init_db()`'s DDL.
- `python-dotenv` — loads `.env` into `os.environ` for local development
  (production platforms like Railway inject env vars directly, no `.env`
  file needed there).
- `supabase` — official Supabase Python client / PostgREST query builder,
  used for all non-DDL data access.

## Rules for implementation

- Use the `supabase-py` query builder for all reads/writes in `seed_db()`
  and `app.py`; only `init_db()` uses raw `psycopg2`/SQL, because
  PostgREST cannot execute DDL. This is an explicit, scoped exception —
  not a reversal of "avoid unnecessary abstractions" elsewhere in this
  project.
- Aggregation (`SUM`, `GROUP BY`) is done client-side in Python after
  fetching matching rows, not via PostgREST's aggregate functions, since
  those require a non-default, per-project Postgres config flag that
  shouldn't be a hidden prerequisite for the app to run.
- Passwords hashed with werkzeug — unchanged, `generate_password_hash` /
  `check_password_hash` logic is untouched by this migration.
- Use CSS variables — never hardcode hex values (no CSS is touched in this
  step, included for completeness).
- All templates extend `base.html` (no templates touched in this step).
- `SUPABASE_KEY` must be the **service_role** secret key, never the
  publishable/anon key — this app does its own session-based auth, not
  Supabase Auth, so it needs a key that bypasses Row Level Security.
  Treat it like a password: never commit the real `.env`, never expose it
  client-side.
- `DATABASE_URL`/`SUPABASE_URL`/`SUPABASE_KEY` must never be committed —
  only `.env.example` (with placeholders) is tracked; the real `.env`
  stays gitignored.
- Keep `init_db()` and `seed_db()` idempotent and safe to call on every
  app startup, exactly as they behave today.

## Definition of done

- [ ] `pip install -r requirements.txt` succeeds with `psycopg2-binary`,
      `python-dotenv`, and `supabase` installed.
- [ ] A `.env` file with real `DATABASE_URL`/`SUPABASE_URL`/`SUPABASE_KEY`
      values (not committed) lets `python app.py` start without errors.
- [ ] On first run against a fresh Supabase project, `init_db()` creates
      the `users` and `expenses` tables and `seed_db()` inserts the demo
      user and sample expenses, verifiable via the Supabase table editor.
- [ ] Registering a new account via `/register` creates a row in the
      Supabase `users` table.
- [ ] Logging in via `/login` with the demo user (`demo@spendly.com` /
      `demo123`) succeeds and loads `/profile` with the seeded expenses
      visible.
- [ ] Adding, editing, and deleting an expense via `/expenses/add`,
      `/expenses/<id>/edit`, and `/expenses/<id>/delete` all persist
      correctly to the Supabase database and are reflected on `/profile`
      after a refresh.
- [ ] Restarting the Flask process does not lose any data (proving storage
      is no longer local-file-based).
- [ ] No raw SQL remains in `app.py`; all non-DDL reads/writes go through
      `supabase-py`'s query builder.
