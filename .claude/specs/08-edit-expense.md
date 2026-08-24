# Spec: Edit Expense

## Overview

This feature implements the "Edit Expense" form, replacing the
`/expenses/<int:id>/edit` placeholder in `app.py`. It lets a logged-in user
update an existing expense they own (amount, category, date, optional
description), reusing the same form layout and validation rules introduced
in Step 7's "Add Expense" feature. This is Step 8 of the Spendly roadmap,
following Add Expense (Step 7), and it is the first step that lets users
modify data they've already created rather than only adding new rows.

## Depends on

- Step 1 — Database Setup (`expenses` table, `database/db.py`)
- Step 2 — Registration
- Step 3 — Login and Logout (session-based auth)
- Step 5 — Profile Backend Routes (`/profile` reads from `expenses`, so
  edited expenses must be reflected there)
- Step 7 — Add Expense (form structure, validation rules, and
  `add_expense.html` layout this feature reuses)

## Routes

- `GET /expenses/<int:id>/edit` — render the edit form pre-filled with the
  expense's current values — logged-in, owner-only
- `POST /expenses/<int:id>/edit` — validate and update the expense, then
  redirect to `/profile` — logged-in, owner-only

Both methods are handled by a single `edit_expense(id)` view, replacing the
current placeholder at `app.py:424-426`. Unauthenticated requests redirect to
`/login`, matching the pattern used by `profile()` and `add_expense()`. If
the expense does not exist, or exists but belongs to a different user, the
route returns a 404 (do not reveal whether the id belongs to someone else).

## Database changes

No new tables or columns. The existing `expenses` table
(`user_id, amount, category, date, description, created_at`) already has
every column this feature needs; the row is updated with `UPDATE`, not
replaced. `_get_profile_transactions()` in `app.py` must additionally select
`id` so `profile.html` can link each row to its edit page — this is a query
change, not a schema change.

## Templates

- **Create:** `templates/edit_expense.html` — same
  `auth-card`/`form-group`/`form-input` structure as `templates/add_expense.html`,
  pre-filled with the expense's current amount, category, date, and
  description, with an `{% if error %}` block for validation failures and a
  submit button labeled "Save changes".
- **Modify:** `templates/profile.html` — add an edit link/icon per row in
  the "Recent transactions" table (around line 76-83), pointing to
  `{{ url_for('edit_expense', id=txn.id) }}`.

## Files to change

- `app.py` — replace the placeholder `edit_expense(id)` route with the real
  `GET`/`POST` implementation and validation logic; update
  `_get_profile_transactions()` to also select `id`.
- `templates/profile.html` — add the per-row edit entry point.
- `static/css/style.css` — add any new styles the edit link/icon needs
  (reuse existing classes where possible).

## Files to create

- `templates/edit_expense.html`

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (n/a to this feature, but preserve existing
  auth code untouched)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Look up the expense with `WHERE id = ? AND user_id = ?` (both the id and
  the logged-in `session["user_id"]`) so one user can never view or edit
  another user's expense; return 404 if no matching row is found.
- Validate `amount` is present and a positive number, `category` is one of
  `CATEGORIES`, and `date` is a valid `YYYY-MM-DD` string not in the future;
  re-render the form with an `error` message and the user's submitted values
  on any failure, following the `add_expense()` error convention (no flash
  messages, no client-side validation framework).
- Scope the `UPDATE` to both `id` and `session["user_id"]` in the `WHERE`
  clause — never trust a client-supplied user id.
- On success, redirect to `/profile` (`redirect(url_for("profile"))`) so the
  updated expense is visible immediately.

## Definition of done

- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`.
- [ ] Visiting `/expenses/<id>/edit` for an expense owned by another user (or
      a non-existent id) returns a 404.
- [ ] Visiting `/expenses/<id>/edit` for your own expense renders a form
      pre-filled with its current amount, category, date, and description.
- [ ] Submitting the form with a valid amount/category/date updates the
      existing row in `expenses` (no new row is inserted).
- [ ] After a successful submit, the browser is redirected to `/profile` and
      the updated values appear in the transactions list and updated
      total-spent/category stats.
- [ ] Submitting with a missing/negative/non-numeric amount re-renders the
      form with an error message and the row is left unchanged.
- [ ] Submitting with an invalid category or malformed date re-renders the
      form with an error message and the row is left unchanged.
- [ ] Each row in the "Recent transactions" table on `/profile` links to its
      own `/expenses/<id>/edit` page.
- [ ] `python app.py` starts without errors and the placeholder text
      "Edit expense — coming in Step 8" no longer appears anywhere.
