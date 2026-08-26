# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

"Spendly" is a Flask-based expense tracker built incrementally as a step-by-step learning project. The `app.py` and `database/db.py` files contain comments like `# Students will write this file in Step 1 — Database Setup` and placeholder routes marked `coming in Step N` — this is intentional scaffolding, not a bug. When asked to implement a route or feature, check for these markers to understand what step is being built and follow the existing code's style rather than jumping ahead to unrequested steps.

## Commands

There is no build step, bundler, or frontend framework — this is server-rendered Flask with vanilla CSS/JS.

```bash
# Activate the virtualenv (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the dev server (http://localhost:5001)
python app.py

# Run tests (pytest-flask is a dependency; no tests/ directory exists yet)
pytest
```

The Flask app runs with `debug=True` on port `5001` (not the default 5000).

## Architecture

- **`app.py`** — single Flask application file with all routes. As the app grows, new routes are added directly here rather than via blueprints — follow this pattern unless asked to refactor.
- **`database/db.py`** — the app's datastore is Supabase Postgres, not local SQLite, exposed via two connection paths: `get_db()` is a raw `psycopg2` connection used **only** by `init_db()` to run `CREATE TABLE IF NOT EXISTS` DDL, since Supabase's REST API has no DDL surface at all; `get_client()` returns a `supabase-py` `Client` (authenticated with the `service_role` secret key) used for everything else — `seed_db()` and every route in `app.py` — via the `.table(...)` query builder rather than raw SQL. This is an explicit, scoped exception for the Supabase REST client on this project, not a blanket "ORMs are fine" policy change. `DATABASE_URL` (pooler connection, for `init_db()`) and `SUPABASE_URL`/`SUPABASE_KEY` (for `get_client()`) are read from a local `.env` (see `.env.example`); never commit the real `.env` or the `service_role` key.
- **`templates/`** — Jinja2 templates. `base.html` is the shared layout (nav, footer, `{% block title/head/content/scripts %}`); page templates `{% extends "base.html" %}` and fill in `content`. Forms POST directly to routes like `/register` and `/login` and render an `{% if error %}` block on failure — follow this convention for new forms rather than introducing flash messages or client-side validation frameworks.
- **`static/css/style.css`** — shared/app styles (nav, footer, auth forms, etc.). **`static/css/landing.css`** — landing-page-specific styles, loaded separately. **`static/js/main.js`** — currently empty; vanilla JS only, no frontend build tooling.
- Currency is displayed in PKR (Pakistani Rupees), not USD/INR — keep this in mind when formatting amounts or writing copy ("Track every rupee...").

## Conventions seen in existing code

- Routes are grouped in `app.py` under comment banners (`# Routes`, `# Placeholder routes — students will implement these`) — keep implemented routes above the placeholder section and remove the placeholder once implemented.
- Auth form inputs use `class="form-input"`/`form-group` and submit buttons use `class="btn-submit"`; reuse these classes rather than inventing new ones for consistent styling.
