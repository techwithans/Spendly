# Spec: Delete Expense

## Overview

This feature implements expense deletion, replacing the
`/expenses/<int:id>/delete` placeholder in `app.py`. It lets a logged-in
user permanently remove an expense they own, with a confirmation step to
guard against accidental clicks, matching the "Edit" entry point already
present on each row of the "Recent transactions" table. This is Step 9 of
the Spendly roadmap, following Add Expense (Step 7) and Edit Expense
(Step 8), and completes basic CRUD on expenses.

## Depends on

- Step 1 — Database Setup (`expenses` table, `database/db.py`)
- Step 2 — Registration
- Step 3 — Login and Logout (session-based auth)
- Step 5 — Profile Backend Routes (`/profile` reads from `expenses`, so a
  deleted expense must disappear from it)
- Step 7 — Add Expense (`_get_profile_transactions()` row shape, `id`
  column already selected as of Step 8)
- Step 8 — Edit Expense (per-row action icon pattern in `profile.html`
  this feature reuses for the delete icon)

## Routes

- `POST /expenses/<int:id>/delete` — delete the expense, then redirect to
  `/profile` — logged-in, owner-only

The current placeholder is a bare `GET` route
(`app.py:505-507`); it is replaced with a `POST`-only route so deletion is
never triggered by a simple link click, prefetch, or crawler — the browser
confirmation dialog (see Templates) submits a small form instead of
navigating directly. Unauthenticated requests redirect to `/login`,
matching `edit_expense()`. If the expense does not exist, or exists but
belongs to a different user, the route returns a 404 (do not reveal
whether the id belongs to someone else).

## Database changes

No database changes. The existing `expenses` table already has everything
needed; the row is removed with `DELETE`, not soft-deleted or flagged.

## Templates

- **Create:** none.
- **Modify:** `templates/profile.html` — add a delete icon next to the
  existing edit icon in the "Recent transactions" table's `txn-actions`
  cell (around line 83-87). It is a small `<form method="post" action="{{ url_for('delete_expense', id=txn.id) }}">`
  wrapping a submit `<button>` (not a link, since the action is now
  `POST`), styled to match `txn-edit-link`. The button carries
  `onclick="return confirm('Delete this expense?')"` — this is the only
  client-side JS the feature needs, consistent with the app's
  no-JS-framework, no-flash-message convention.

## Files to change

- `app.py` — replace the placeholder `delete_expense(id)` route with the
  real `POST` implementation.
- `templates/profile.html` — add the per-row delete form/icon.
- `static/css/style.css` — add a `txn-delete-link` (or shared
  `txn-action-link`) style using `var(--danger)` for the hover state, and
  reset default `<button>` styling (background/border/font) so it matches
  the existing icon-link look.

## Files to create

None.

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (n/a to this feature, but preserve
  existing auth code untouched)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html` (n/a here — only `profile.html`, which
  already does, is touched)
- Scope the `DELETE` to both `id` and `session["user_id"]` in the `WHERE`
  clause — never trust a client-supplied user id — e.g.
  `DELETE FROM expenses WHERE id = ? AND user_id = ?`.
- Before deleting, look up the expense with `WHERE id = ? AND user_id = ?`
  (or check `cursor.rowcount` after the `DELETE`) and return 404 if no
  matching row exists, so one user can never delete another user's expense
  or probe for the existence of an id.
- No confirmation page/route — confirmation happens client-side via
  `confirm()` before the form submits, per the Templates section above.
- On success, redirect to `/profile` (`redirect(url_for("profile"))`) so
  the removed expense is gone from the list immediately.

## Definition of done

- [ ] Visiting `/expenses/<id>/delete` with `GET` returns a 405 (route is
      `POST`-only).
- [ ] Submitting the delete form while logged out redirects to `/login`.
- [ ] Submitting the delete form for an expense owned by another user (or
      a non-existent id) returns a 404 and does not delete anything.
- [ ] Submitting the delete form for your own expense removes it from the
      `expenses` table (verify the row count decreases by exactly one).
- [ ] After a successful delete, the browser is redirected to `/profile`
      and the deleted expense no longer appears in the transactions list,
      and total-spent/category stats reflect its removal.
- [ ] Each row in the "Recent transactions" table on `/profile` shows a
      delete icon next to the edit icon, and clicking it prompts a
      confirm dialog before submitting.
- [ ] Cancelling the confirm dialog leaves the expense untouched.
- [ ] `python app.py` starts without errors and the placeholder text
      "Delete expense — coming in Step 9" no longer appears anywhere.
