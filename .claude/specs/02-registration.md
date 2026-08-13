# Spec: Registration

## Overview

Implement account creation so a visitor can turn the existing `register.html` form into a real signup flow. This is the first authentication step built on top of the Step 1 database layer: it wires `POST /register` to validate input, hash the password, and insert a new row into `users`. Session-based login and `/logout` are out of scope here — they belong to a later "Login and Logout" step — so a successful registration redirects to the sign-in page rather than establishing a session.

## Depends on

- Step 1 — Database Setup (`database/db.py`: `get_db()`, `init_db()`, `users` table)

## Routes

- `POST /register` — validate and create a new user, then redirect to `/login` on success or re-render `register.html` with an error — public
- `GET /register` — unchanged, already implemented

## Database changes

No database changes. The existing `users` table (`id`, `name`, `email`, `password_hash`, `created_at`) already supports registration as defined in `database/db.py`.

## Templates

- **Create:** none
- **Modify:** `templates/register.html` — reuse the existing `{% if error %}` block and field names (`name`, `email`, `password`) as-is; add sticky values (`value="{{ name }}"`, `value="{{ email }}"`) to the name and email inputs so the form isn't wiped on a validation error; add a new `confirm_password` field (same `form-group`/`form-input` markup as the existing password field, labeled "Confirm password", placed directly after it) so the user types their password twice

## Files to change

- `app.py` — add `methods=["GET", "POST"]` to the `/register` route and implement validation, password hashing, and insert logic

## Files to create

None.

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Validate on the server: name and email required (non-empty after `.strip()`), email contains `@`, password is at least 8 characters
- Require `confirm_password` and check it matches `password` exactly (before the length check, so a mismatch is reported clearly rather than as a generic length error); on mismatch show `"Passwords do not match."` and re-render with the sticky name/email (never re-populate either password field)
- Normalize email to `email.strip().lower()` before both the uniqueness check and the insert, so the `UNIQUE` constraint and the pre-check agree on case and `Test@x.com` / `test@x.com` can't both register
- Check for an existing (normalized) email before inserting and show a friendly error ("An account with this email already exists.") rather than letting the `UNIQUE` constraint raise an unhandled `sqlite3.IntegrityError`; also catch `sqlite3.IntegrityError` around the insert itself as a backstop against a race between the check and the insert
- Never store or log a plaintext password
- On success, redirect with `redirect(url_for('login'))` — do not set a session (no session support exists yet)

## Definition of done

- [ ] Submitting the register form with valid name/email/password creates a row in `users` with a hashed (not plaintext) password
- [ ] Submitting with an email that already exists shows an error on `register.html` and does not create a duplicate row
- [ ] Submitting with a password under 8 characters shows an error and does not create a row
- [ ] Submitting with `password` and `confirm_password` that don't match shows a "Passwords do not match." error and does not create a row
- [ ] Submitting with an empty name or malformed email shows an error and does not create a row
- [ ] A successful registration redirects to `/login`
- [ ] Registering the demo seed email (`demo@spendly.com`) is rejected as a duplicate
- [ ] App starts and `/register` still renders correctly on `GET`
