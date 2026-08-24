# Spec: Add Expense

## Overview

This feature implements the "Add Expense" form, replacing the `/expenses/add`
placeholder in `app.py`. It lets a logged-in user record a new expense
(amount, category, date, optional description) which is inserted into the
existing `expenses` table and immediately reflected in the profile page's
stats, transactions, and category breakdown. This is Step 7 of the Spendly
roadmap, following the profile page and its date filter (Steps 4–6), and it
is the first step that lets users create their own data rather than only
viewing seeded data.

## Depends on

- Step 1 — Database Setup (`expenses` table, `database/db.py`)
- Step 2 — Registration
- Step 3 — Login and Logout (session-based auth)
- Step 5 — Profile Backend Routes (`/profile` reads from `expenses`, so newly
  added expenses must appear there)

## Routes

- `GET /expenses/add` — render the add-expense form — logged-in
- `POST /expenses/add` — validate and insert a new expense, then redirect to
  `/profile` — logged-in

Both methods are handled by a single `add_expense()` view, replacing the
current placeholder at `app.py:357-359`. Unauthenticated requests redirect to
`/login`, matching the pattern used by `profile()` and `analytics()`.

## Database changes

No database changes. The existing `expenses` table
(`user_id, amount, category, date, description, created_at`) already has
every column this feature needs. The category `<select>` options come from
the existing `CATEGORIES` list in `database/db.py` — no new table or enum.

## Templates

- **Create:** `templates/add_expense.html` — form with amount, category
  (`<select>` populated from `CATEGORIES`), date (defaulting to today), and
  optional description fields, following the `auth-card`/`form-group`/
  `form-input` structure used in `register.html` and `login.html`, with an
  `{% if error %}` block for validation failures.
- **Modify:** `templates/profile.html` — add an "Add Expense" link/button
  (e.g. in `.profile-header`) pointing to `{{ url_for('add_expense') }}`,
  since no route currently links to this page.

## Files to change

- `app.py` — replace the placeholder `add_expense()` route with the real
  `GET`/`POST` implementation and validation logic.
- `templates/profile.html` — add the "Add Expense" entry point.
- `static/css/style.css` — add any new styles the button/entry point needs
  (reuse existing `.btn-primary`/`.btn-submit` classes where possible).

## Files to create

- `templates/add_expense.html`

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (n/a to this feature, but preserve existing
  auth code untouched)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Validate `amount` is present and a positive number, `category` is one of
  `CATEGORIES`, and `date` is a valid `YYYY-MM-DD` string not in the future;
  re-render the form with an `error` message and the user's submitted values
  on any failure, following the `register()`/`login()` error convention
  (no flash messages, no client-side validation framework).
- Scope the `INSERT` to `session["user_id"]` — never trust a client-supplied
  user id.
- On success, redirect to `/profile` (`redirect(url_for("profile"))`) so the
  new expense is visible immediately.

## Definition of done

- [ ] Visiting `/expenses/add` while logged out redirects to `/login`.
- [ ] Visiting `/expenses/add` while logged in renders a form with amount,
      category, date, and description fields.
- [ ] Submitting the form with a valid amount/category/date creates a new
      row in `expenses` scoped to the logged-in user's `user_id`.
- [ ] After a successful submit, the browser is redirected to `/profile` and
      the new expense appears in the transactions list and updates the
      total-spent/category stats.
- [ ] Submitting with a missing/negative/non-numeric amount re-renders the
      form with an error message and no row is inserted.
- [ ] Submitting with an invalid category or malformed date re-renders the
      form with an error message and no row is inserted.
- [ ] The "Add Expense" link on `/profile` navigates to `/expenses/add`.
- [ ] `python app.py` starts without errors and the placeholder text
      "Add expense — coming in Step 7" no longer appears anywhere.
