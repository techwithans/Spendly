# Spec: Analytics Page

## Overview

Spendly already has an `/analytics` route, but it renders a static "Coming Soon"
placeholder (`templates/analytics.html`). This step turns it into a real
spending-analytics dashboard for the logged-in user. The page summarises the
user's entire expense history into four read-only sections: a headline stat row
(total spent, transaction count, average transaction, average monthly spend), a
six-month spending-trend bar chart, an all-time category breakdown, and a
"this month vs last month" comparison with a single biggest-expense highlight.
Like the profile page, all aggregation is done in Python over rows fetched with
the Supabase REST client — there is no charting library and no frontend build
step; the trend chart is plain CSS bars.

## Depends on

- Step 1: Database setup (`users` / `expenses` tables, `get_db()` / `init_db()`)
- Step 2: Registration (accounts must exist to have data)
- Step 3: Login + Logout (session `user_id` identifies whose data to load)
- Step 5: Profile backend routes (`_get_profile_*` helpers and the
  `"PKR {:,.0f}"` / `cat-<name>` / `bar-w-<n>` conventions this step reuses)
- Step 10: Connect Supabase (`get_client()` and the `.table(...)` query builder)

## Routes

- `GET /analytics` — render the analytics dashboard for `session["user_id"]` —
  logged-in only (redirect to `/login` if not authenticated).

No new routes. Only the body of the existing `analytics()` view changes; the
URL, method, and endpoint name stay the same. This route stays above the
placeholder section in `app.py` — it is already implemented, so there is no
placeholder banner to remove.

## Database changes

No database changes. Every value on the page is derived from existing
`expenses` columns (`amount`, `category`, `date`) scoped to the current user.

## Templates

- **Create:** None.
- **Modify:** `templates/analytics.html` — replace the entire `coming-soon`
  markup inside `{% block content %}` with the real dashboard. Keep
  `{% extends "base.html" %}` and the `{% block title %}Analytics — Spendly{% endblock %}`.
  The nav link in `base.html` already points here and already gets its active
  state from `request.endpoint == 'analytics'` — no `base.html` change needed.

  Sections, in order:
  1. **Header** — page heading ("Analytics") and a short subheading; an
     "Add Expense" link styled `btn-primary` (mirror the profile header action).
  2. **Stat row** — four `stat-tile` cards (reuse the profile `stat-tile` /
     `stat-label` / `stat-value` classes): Total spent, Transactions,
     Average transaction, Average monthly spend.
  3. **Spending trend** — a `profile-panel` containing a bar chart of the last
     six calendar months (oldest → newest, current month last). Each bar is a
     `<div>` whose height comes from a `bar-h-<n>` utility class (see CSS),
     never an inline style; each column shows the month label (e.g. "Mar") and
     the formatted amount. A month with no spend renders a zero-height bar.
  4. **Category breakdown** — a `profile-panel` reusing the exact
     `category-breakdown` / `category-row` / `category-bar` / `cat-<name>` /
     `bar-w-<n>` markup from `profile.html`, one row per category the user has
     ever spent in, ordered by amount descending.
  5. **Month comparison** — a `profile-panel` showing this-month total vs
     last-month total side by side, plus a percentage-change indicator with an
     up/down Lucide icon and a `trend-up` / `trend-down` / `trend-flat` class
     for colour. Below it, a single "Biggest expense" line: amount, category
     badge, description, and human date of the user's largest single expense
     (omit the line entirely if the user has no expenses).

  Empty state: if the user has zero expenses, render a single centered
  `profile-panel` with a short "No expenses yet — add one to see your
  analytics." message and an "Add Expense" button instead of the five sections.

## Files to change

- `app.py`
  - Rewrite the `analytics()` view body to load real data for
    `session["user_id"]` via `get_client()` and pass it to the template.
  - Add an analytics helper section (comment banner, next to the profile
    helpers) with small single-purpose functions, following the
    `_get_profile_*` style:
    - `_analytics_summary(rows)` → `{"total_spent", "transaction_count",
      "avg_transaction", "avg_monthly"}`, all money values formatted
      `"PKR {:,.0f}"`; must not divide by zero.
    - `_analytics_monthly(rows)` → list of exactly 6 dicts
      `{"label": "Mar", "amount": "PKR 12,400", "bar_class": "bar-h-65"}`
      for the last 6 calendar months ending with the current month.
      `bar_class` is the nearest `bar-h-<n>` class to that month's share of
      the six-month maximum (so the tallest bar is `bar-h-100`); all-zero
      months give `bar-h-0`.
    - `_analytics_categories(rows)` → same shape and `bar_class` logic as
      `_get_profile_categories` (reuse that function directly if practical
      rather than copying it).
    - `_analytics_month_comparison(rows)` → `{"this_month", "last_month",
      "change_pct", "trend"}` where `trend` is `"up"`, `"down"`, or `"flat"`
      and `change_pct` is an integer percentage (0 when last month was 0).
    - `_analytics_biggest(rows)` → `None` or
      `{"amount", "category", "description", "date"}` with `amount` formatted
      `"PKR {:,.0f}"` and `date` formatted like the profile table ("Aug 12").
  - Fetch the user's expense rows once
    (`get_client().table("expenses").select("amount, category, date, description")
    .eq("user_id", user_id).execute().data`) and pass that list to each helper,
    matching the client-side-aggregation approach already used by
    `_get_profile_stats` (PostgREST aggregate functions are not enabled on this
    project).
- `templates/analytics.html` — see Templates section.
- `static/css/style.css`
  - Add an "Analytics" section with styles for the trend chart (chart wrapper,
    bar column, bar, month label, amount label) and the month-comparison block
    (`trend-up` / `trend-down` / `trend-flat` using `--accent` / `--danger` /
    `--ink-muted`).
  - Add `bar-h-<n>` height utilities in steps of 5 from `bar-h-0` to
    `bar-h-100` (`.bar-h-0 { height: 0; } … .bar-h-100 { height: 100%; }`),
    mirroring the existing `bar-w-<n>` block just above.
  - Remove the now-dead `.coming-soon-*` rules (and their entries in the two
    responsive `@media` blocks) — `analytics.html` was their only consumer.
  - Reuse existing responsive breakpoints; the stat row and trend chart must
    not overflow horizontally on mobile.

## Files to create

None.

## New dependencies

No new dependencies. No charting library — the trend chart is CSS bars only.

## Rules for implementation

- No SQLAlchemy or ORMs — data access is the Supabase REST client
  (`get_client().table(...)`), consistent with the rest of `app.py`.
- Parameterised queries only — filter with `.eq("user_id", session["user_id"])`;
  never string-format the user id or any value into a query.
- Passwords hashed with werkzeug (unchanged in this step).
- Use CSS variables — never hardcode hex values; category colours come from the
  existing `--color-<category>` vars via the `cat-<name>` classes.
- All templates extend `base.html`.
- Every query must scope to the current user — `/analytics` must never show
  another user's expenses or totals.
- No inline styles — bar heights and widths come from `bar-h-<n>` / `bar-w-<n>`
  classes, not `style="..."`.
- All month/percentage/average maths happens in `app.py`, not in the template.
- Currency is PKR, formatted `"PKR {:,.0f}"` everywhere, matching the profile page.
- Handle the zero-expense and single-month cases without raising (no division by
  zero, no `max()` on an empty sequence).
- Keep helper functions small and single-purpose with docstrings, matching the
  `_get_profile_*` style already in `app.py`.

## Definition of done

- [ ] Visiting `/analytics` while logged out redirects to `/login`
- [ ] Visiting `/analytics` as the seeded demo user (`demo@spendly.com` /
      `demo123`) returns HTTP 200 and shows the dashboard, not "Coming Soon"
- [ ] "Total spent" equals the sum of the demo user's `expenses.amount`, and
      "Transactions" equals their row count
- [ ] "Average transaction" equals total ÷ transaction count, and
      "Average monthly spend" is a sensible non-zero figure
- [ ] The spending-trend chart shows exactly six month columns ending with the
      current month, with bar heights proportional to each month's spend and the
      tallest month at full height
- [ ] The category breakdown lists one row per category the demo user has spent
      in, ordered by amount descending, with bar widths reusing `bar-w-<n>`
      classes and amounts that sum to "Total spent"
- [ ] The month-comparison block shows this-month and last-month totals with a
      correct up/down/flat indicator and percentage
- [ ] "Biggest expense" shows the demo user's single largest expense (amount,
      category badge, description, date)
- [ ] A freshly registered user with no expenses sees the empty-state panel and
      an "Add Expense" button — no errors, no divide-by-zero
- [ ] No other user's data appears on the page for any logged-in user
- [ ] `grep -n "coming-soon" static/css/style.css templates/analytics.html`
      returns nothing
- [ ] No inline `style="..."` attributes were added to `analytics.html`
- [ ] The page has no horizontal scroll at 375px width
