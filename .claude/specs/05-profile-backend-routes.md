# Spec: Profile Page Backend Routes

## Overview

Step 4 built `templates/profile.html` and the `/profile` view with fully hardcoded Python dicts/lists standing in for real data. This step wires that view up to the actual database: the user info card, summary stats, transaction history, and category breakdown must all be computed from the logged-in user's rows in the `users` and `expenses` tables via `get_db()`. No template changes are required — the existing `profile.html` already consumes `user`, `stats`, `transactions`, and `categories` in the shapes described below, so this step is purely about replacing the hardcoded context in `app.py` with real queries.

## Depends on

- Step 1: Database setup (`users` and `expenses` tables, `get_db()`)
- Step 2: Registration (user accounts must exist to have data to query)
- Step 3: Login + Logout (session `user_id` identifies which user's data to load)
- Step 4: Profile page design (`templates/profile.html` and the `/profile` route stub already exist)

## Routes

- `GET /profile` — render the profile page using real data queried for `session["user_id"]` — logged-in only (redirect to `/login` if not authenticated). No change to the route signature or URL; only the body of the existing view function changes.

If no new routes: N/A — this modifies the existing `/profile` route only.

## Database changes

No database changes. The existing `users` and `expenses` tables (and their columns) are sufficient for every value the template needs.

## Templates

- **Create:** None.
- **Modify:** None. `templates/profile.html` already expects `user`, `stats`, `transactions`, and `categories` in the exact shapes produced below — no edits needed as long as the view supplies matching data.

## Files to change

- `app.py` — replace the hardcoded `user`, `stats`, `transactions`, and `categories` values inside `profile()` with values derived from real queries:
  - `user`: look up `name`, `email`, `created_at` from `users` for `session["user_id"]`; derive `initials` from `name` in Python (e.g. first letters of first/last word); format `created_at` into a `"Month YYYY"` string (e.g. "August 2026") for `member_since`.
  - `stats.total_spent`: `SUM(amount)` over the user's expenses, formatted as `"PKR {:,.0f}".format(...)` (or `"PKR 0"` if the user has no expenses).
  - `stats.transaction_count`: `COUNT(*)` over the user's expenses.
  - `stats.top_category`: category with the highest summed `amount` for the user (empty string or `"—"` if no expenses).
  - `transactions`: the user's most recent expenses (e.g. `ORDER BY date DESC, id DESC LIMIT 5`), each row formatted with a human-readable `date` (e.g. "Aug 12"), `description`, `category`, and `amount` formatted as `"PKR {:,.0f}"`.
  - `categories`: per-category totals for the user, one row per category that has at least one expense, each with `name`, `amount` (formatted `"PKR {:,.0f}"`), and a `bar_class` computed in Python from that category's share of the user's total spend (reuse the existing `bar-w-<n>` CSS class naming already present in `static/css/style.css`, rounding the percentage to the nearest value with an existing class, or the nearest 2).
  - All queries must use `get_db()` with parameterised SQL (`?` placeholders) and must filter by `user_id = ?` using `session["user_id"]`.

## Files to create

None.

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only — never string-format SQL, especially not `user_id`
- Passwords hashed with werkzeug (unchanged in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Every query must scope to `WHERE user_id = ?` with `session["user_id"]` — never return another user's data
- Close every `get_db()` connection after use (`conn.close()`), consistent with `register()` and `login()`
- Handle the zero-expenses case without raising (e.g. `SUM(amount)` returning `NULL` from SQLite must not crash `"PKR {:,.0f}".format(...)`)
- Category badge and bar CSS classes (`cat-<lowercase-category>`, `bar-w-<n>`) must continue to be plain CSS classes, not inline styles — reuse whatever `bar-w-*` classes already exist in `static/css/style.css` rather than inventing new ones inline

## Definition of done

- [ ] Visiting `/profile` without being logged in still redirects to `/login`
- [ ] Visiting `/profile` while logged in as the seeded demo user (`demo@spendly.com` / `demo123`) returns HTTP 200
- [ ] The user info card shows the real name, email, and a `member_since` date derived from `users.created_at`
- [ ] `stats.total_spent` equals the actual sum of the demo user's `expenses.amount`
- [ ] `stats.transaction_count` equals the actual count of the demo user's expense rows
- [ ] `stats.top_category` matches the category with the highest summed amount for the demo user
- [ ] The transaction table shows real rows from `expenses`, most recent first, limited to a small fixed number
- [ ] The category breakdown shows one row per category the demo user has spent in, with amounts that sum to `stats.total_spent`
- [ ] Registering a second user with no expenses and visiting their `/profile` does not error (zero-expense case handled gracefully)
- [ ] No other user's expenses ever appear on a given user's profile page
