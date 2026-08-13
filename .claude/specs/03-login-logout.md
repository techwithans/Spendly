# Spec: Login and Logout

## Overview

Wire up real session-based authentication on top of the existing `login.html` form and `users` table. Today `GET /login` just renders the form and `/logout` is a placeholder string. This step makes `POST /login` verify credentials against the hashed password created during registration, establish a Flask session on success, and makes `/logout` clear that session. It also makes the shared nav (`base.html`) aware of whether a visitor is signed in, since that's the only place session state becomes visible across the app, and makes `/login` and `/register` redirect an already-signed-in visitor away instead of showing them an auth form they no longer need. Protecting other routes (e.g. profile, expenses) behind login is out of scope — those stay placeholders until their own steps.

## Depends on

- Step 1 — Database Setup (`database/db.py`: `get_db()`, `users` table)
- Step 2 — Registration (`users.password_hash` populated via `generate_password_hash`)

## Routes

- `POST /login` — verify email/password against `users`, establish a session, redirect to `/` on success or re-render `login.html` with an error — public
- `GET /login` — renders the form as before, but if `session.user_id` is already set, redirect to `/` instead — public (redirects away when authenticated)
- `GET /logout` — clear the session and redirect to `/` — logged-in (safe to hit while logged out too; it just becomes a no-op redirect)
- `GET /register`, `POST /register` — unchanged except: if `session.user_id` is already set, redirect to `/` instead of rendering/processing the form — public (redirects away when authenticated)

## Database changes

No database changes. The existing `users` table (`id`, `name`, `email`, `password_hash`) already supports login as defined in `database/db.py`.

## Templates

- **Create:** none
- **Modify:**
  - `templates/login.html` — reuse the existing `{% if error %}` block and field names (`email`, `password`) as-is; add a sticky value (`value="{{ email }}"`) to the email input so it isn't wiped on a failed login (never re-populate the password field)
  - `templates/base.html` — make the `nav-links` block conditional on `session.user_id`: logged-out visitors keep seeing "Sign in" / "Get started" exactly as today; logged-in visitors instead see their name (plain text, not a link) and a "Logout" link pointing to `{{ url_for('logout') }}`

## Files to change

- `app.py` — set `app.secret_key`, add `methods=["POST"]` handling to `/login`, implement session creation, implement `/logout`, remove both from the placeholder section, add an already-logged-in guard to the top of `login()` and `register()`
- `templates/login.html` — sticky email value on error
- `templates/base.html` — conditional nav based on session

## Files to create

None.

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords verified with werkzeug (`check_password_hash`) — never compare plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Set `app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")` near the top of `app.py`, right after `app = Flask(__name__)` — sessions can't be signed without it
- Normalize the submitted email the same way registration does (`.strip().lower()`) before looking it up, so case never blocks a valid login
- On login, look up the user by normalized email; if no row matches, or `check_password_hash` fails, show one generic error — `"Invalid email or password."` — on both failure modes so the response never reveals whether an email is registered
- On success, store only `session["user_id"]` and `session["name"]` — never put `password_hash` or the raw row into the session
- On success, `redirect(url_for('landing'))` — there's no dashboard/home page yet (`/profile` is still a Step 4 placeholder), so a signed-in user lands back on `/` with the nav now showing their name and Logout
- `GET /logout` calls `session.clear()` then `redirect(url_for('landing'))`, regardless of whether a session existed
- `base.html`'s conditional nav reads `session.user_id` / `session.name` directly (Jinja has access to `session` by default) — no new context processor needed
- Do not add a `login_required` decorator or protect `/profile` or `/expenses/*` in this step — there is nothing behind them yet, and gating them is a later step's concern
- At the top of both `login()` and `register()`, before handling `GET` or `POST`, check `if session.get("user_id")` and `redirect(url_for('landing'))` if so — an already-authenticated visitor should never see or submit either auth form again

## Definition of done

- [ ] Submitting `/login` with the seeded demo account (`demo@spendly.com` / `demo123`) redirects to `/` and sets a session cookie
- [ ] Submitting `/login` with a correct email but wrong password shows `"Invalid email or password."` and does not redirect
- [ ] Submitting `/login` with an email that doesn't exist shows the same `"Invalid email or password."` message (no distinct "user not found" text)
- [ ] Submitting `/login` with mismatched email case (e.g. `Demo@Spendly.com`) still logs in successfully
- [ ] After a successful login, the nav on any page shows the user's name and a "Logout" link instead of "Sign in" / "Get started"
- [ ] Visiting `/logout` while logged in clears the session, redirects to `/`, and the nav reverts to "Sign in" / "Get started"
- [ ] Visiting `/logout` while logged out doesn't error — it just redirects to `/`
- [ ] App starts and `/login` still renders correctly on `GET` while logged out
- [ ] While logged in, visiting `/login` redirects to `/` instead of showing the form
- [ ] While logged in, visiting `/register` redirects to `/` instead of showing the form
