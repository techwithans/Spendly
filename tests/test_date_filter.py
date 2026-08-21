"""
Tests for the date-range filter added to `GET /profile` (Step 6).

Scope: only the filtering behavior layered on top of the existing Step 5
profile page (stats / transactions / category breakdown). Auth-guard and
non-filter profile rendering are assumed to already be covered by
tests/test_profile.py (Step 5) — here we only add a minimal auth-guard
check to confirm the filter query params don't bypass it.

Behavior contract under test (see task description — NOT the stale spec
file at .claude/specs/06-date-filter-profile-page.md, which mentions a
database/queries.py module, a "₹" currency symbol, and flash-message
banners, none of which exist in this codebase):

- date_from / date_to are optional ISO `YYYY-MM-DD` query params.
- Only one present, or both malformed, or date_from > date_to -> silently
  fall back to the unfiltered "all time" view. No 500s, no error banners.
- Both present, valid, date_from <= date_to -> stats/transactions/
  categories restricted to date >= date_from AND date <= date_to
  (inclusive on both ends).
- Currency is always formatted as "PKR {:,.0f}".format(amount) — never a
  Rupee sign or any other symbol.
- Zero matching expenses -> 200 OK, total "PKR 0", transaction_count "0",
  top_category "—" (em dash), no transaction rows, no category rows.
- Never leaks another user's expenses.
- Page includes filter-bar / filter-chip markers, four preset chips
  (This Month, Last 3 Months, Last 6 Months, All Time), and a custom
  <form method="get"> with date_from / date_to <input type="date">
  fields.

Notes on fixtures:
`database/db.py`'s `get_db()` reads a module-level `DB_PATH` constant
(not `app.config['DATABASE']`) and always points at a single file on
disk. To get per-test isolation we monkeypatch `database.db.DB_PATH` to
a fresh temp file before calling `init_db()`. Because `get_db()` looks
up `DB_PATH` as a module global at call time, this works regardless of
how other modules imported `get_db`.
"""

import os
import re
import sys

import pytest

# Ensure the project root (parent of tests/) is importable regardless of
# how pytest is invoked (plain `pytest` does not add cwd to sys.path the
# way `python -m pytest` does).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database.db as db_module
from app import app as flask_app

DEFAULT_PASSWORD = "password123"


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #

@pytest.fixture
def app(tmp_path, monkeypatch):
    db_path = tmp_path / "test_spendly.db"
    monkeypatch.setattr(db_module, "DB_PATH", str(db_path))
    db_module.init_db()

    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret",
    })
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #

def register(client, name, email, password=DEFAULT_PASSWORD):
    return client.post(
        "/register",
        data={
            "name": name,
            "email": email,
            "password": password,
            "confirm_password": password,
        },
        follow_redirects=True,
    )


def login(client, email, password=DEFAULT_PASSWORD):
    return client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def register_and_login(client, name, email, password=DEFAULT_PASSWORD):
    register(client, name, email, password)
    login(client, email, password)
    return get_user_id(email)


def get_user_id(email):
    conn = db_module.get_db()
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    assert row is not None, f"Expected a user row for {email}"
    return row["id"]


def insert_expense(user_id, amount, category, date_str, description):
    conn = db_module.get_db()
    conn.execute(
        "INSERT INTO expenses (user_id, amount, category, date, description) "
        "VALUES (?, ?, ?, ?, ?)",
        (user_id, amount, category, date_str, description),
    )
    conn.commit()
    conn.close()


def html_of(response):
    return response.get_data(as_text=True)


def parse_stats(html):
    """Extract [total_spent, transaction_count, top_category] in template order."""
    values = re.findall(r'<span class="stat-value">(.*?)</span>', html, re.S)
    assert len(values) == 3, f"Expected 3 stat-value spans, found {len(values)}"
    return {
        "total_spent": values[0].strip(),
        "transaction_count": values[1].strip(),
        "top_category": values[2].strip(),
    }


def parse_transaction_rows(html):
    tbody_match = re.search(r"<tbody>(.*?)</tbody>", html, re.S)
    tbody = tbody_match.group(1) if tbody_match else ""
    return re.findall(r"<tr>(.*?)</tr>", tbody, re.S)


def parse_category_names(html):
    return re.findall(r'<span class="category-name">(.*?)</span>', html, re.S)


# --------------------------------------------------------------------- #
# Shared test data: one user (A) with a spread of dated expenses.
# --------------------------------------------------------------------- #

def seed_user_a_expenses(user_id):
    insert_expense(user_id, 500, "Food", "2026-01-01", "A-Jan1-Food")
    insert_expense(user_id, 734, "Transport", "2026-01-15", "A-Jan15-Transport")
    insert_expense(user_id, 300, "Bills", "2026-01-31", "A-Jan31-Bills")
    insert_expense(user_id, 999, "Shopping", "2026-02-01", "A-Feb1-Shopping")
    # all-time total = 2533, Jan-only total = 1534


@pytest.fixture
def user_a(client):
    user_id = register_and_login(client, "User A", "usera@example.com")
    seed_user_a_expenses(user_id)
    return client, user_id


# --------------------------------------------------------------------- #
# Auth guard (filter params must not bypass login requirement)
# --------------------------------------------------------------------- #

class TestAuthGuard:
    def test_profile_with_filter_params_requires_login(self, client):
        resp = client.get("/profile?date_from=2026-01-01&date_to=2026-01-31")
        assert resp.status_code == 302, "Unauthenticated /profile should redirect"
        assert "/login" in resp.headers.get("Location", ""), (
            "Unauthenticated /profile should redirect to /login even with filter params"
        )


# --------------------------------------------------------------------- #
# No params / partial params -> unfiltered "all time" view
# --------------------------------------------------------------------- #

class TestUnfilteredFallback:
    def test_no_params_shows_all_time_totals(self, user_a):
        client, _ = user_a
        resp = client.get("/profile")
        assert resp.status_code == 200
        stats = parse_stats(html_of(resp))
        assert stats["total_spent"] == "PKR 2,533"
        assert stats["transaction_count"] == "4"
        assert stats["top_category"] == "Shopping"

    def test_only_date_from_present_is_unfiltered(self, user_a):
        client, _ = user_a
        resp = client.get("/profile?date_from=2026-01-15")
        assert resp.status_code == 200
        stats = parse_stats(html_of(resp))
        assert stats["total_spent"] == "PKR 2,533", (
            "A single date_from with no date_to must not filter"
        )
        assert stats["transaction_count"] == "4"

    def test_only_date_to_present_is_unfiltered(self, user_a):
        client, _ = user_a
        resp = client.get("/profile?date_to=2026-01-15")
        assert resp.status_code == 200
        stats = parse_stats(html_of(resp))
        assert stats["total_spent"] == "PKR 2,533", (
            "A single date_to with no date_from must not filter"
        )
        assert stats["transaction_count"] == "4"

    def test_empty_date_from_with_valid_date_to_is_unfiltered(self, user_a):
        client, _ = user_a
        resp = client.get("/profile?date_from=&date_to=2026-01-31")
        assert resp.status_code == 200
        stats = parse_stats(html_of(resp))
        assert stats["total_spent"] == "PKR 2,533"


# --------------------------------------------------------------------- #
# Valid, complete range -> filtered totals, inclusive on both ends
# --------------------------------------------------------------------- #

class TestValidRangeFiltering:
    def test_full_january_range_filters_out_february_expense(self, user_a):
        client, _ = user_a
        resp = client.get("/profile?date_from=2026-01-01&date_to=2026-01-31")
        assert resp.status_code == 200
        html = html_of(resp)
        stats = parse_stats(html)
        assert stats["total_spent"] == "PKR 1,534"
        assert stats["transaction_count"] == "3"
        assert stats["top_category"] == "Transport"

        assert "A-Jan1-Food" in html
        assert "A-Jan15-Transport" in html
        assert "A-Jan31-Bills" in html
        assert "A-Feb1-Shopping" not in html, "Feb expense must be excluded"

        rows = parse_transaction_rows(html)
        assert len(rows) == 3

    def test_date_from_boundary_is_inclusive(self, user_a):
        client, _ = user_a
        resp = client.get("/profile?date_from=2026-01-01&date_to=2026-01-01")
        assert resp.status_code == 200
        html = html_of(resp)
        stats = parse_stats(html)
        assert stats["total_spent"] == "PKR 500"
        assert stats["transaction_count"] == "1"
        assert stats["top_category"] == "Food"
        assert "A-Jan1-Food" in html
        assert "A-Jan15-Transport" not in html

    def test_date_to_boundary_is_inclusive(self, user_a):
        client, _ = user_a
        resp = client.get("/profile?date_from=2026-01-31&date_to=2026-01-31")
        assert resp.status_code == 200
        html = html_of(resp)
        stats = parse_stats(html)
        assert stats["total_spent"] == "PKR 300"
        assert stats["transaction_count"] == "1"
        assert "A-Jan31-Bills" in html

    def test_range_excluding_day_before_and_after_boundaries(self, user_a):
        client, _ = user_a
        # One day tighter than the full January range on both ends should
        # drop the Jan 1 and Jan 31 expenses, keeping only Jan 15.
        resp = client.get("/profile?date_from=2026-01-02&date_to=2026-01-30")
        assert resp.status_code == 200
        html = html_of(resp)
        stats = parse_stats(html)
        assert stats["total_spent"] == "PKR 734"
        assert stats["transaction_count"] == "1"
        assert "A-Jan15-Transport" in html
        assert "A-Jan1-Food" not in html
        assert "A-Jan31-Bills" not in html


# --------------------------------------------------------------------- #
# Malformed / invalid input -> silent fallback, never a 500 or a banner
# --------------------------------------------------------------------- #

class TestInvalidInputFallsBackSilently:
    def test_malformed_date_from_falls_back_to_all_time(self, user_a):
        client, _ = user_a
        resp = client.get("/profile?date_from=not-a-date&date_to=2026-01-31")
        assert resp.status_code == 200
        stats = parse_stats(html_of(resp))
        assert stats["total_spent"] == "PKR 2,533"
        assert stats["transaction_count"] == "4"

    def test_malformed_date_to_falls_back_to_all_time(self, user_a):
        client, _ = user_a
        resp = client.get("/profile?date_from=2026-01-01&date_to=banana")
        assert resp.status_code == 200
        stats = parse_stats(html_of(resp))
        assert stats["total_spent"] == "PKR 2,533"

    def test_inverted_range_falls_back_to_all_time(self, user_a):
        client, _ = user_a
        resp = client.get("/profile?date_from=2026-01-31&date_to=2026-01-01")
        assert resp.status_code == 200
        html = html_of(resp)
        stats = parse_stats(html)
        assert stats["total_spent"] == "PKR 2,533", (
            "Inverted date_from > date_to must fall back to all-time"
        )
        # This app has no flash-message system at all.
        assert "flash" not in html.lower()

    def test_sql_injection_attempt_does_not_crash_or_drop_data(self, user_a):
        client, user_id = user_a
        resp = client.get(
            "/profile",
            query_string={
                "date_from": "2026-01-01'; DROP TABLE expenses; --",
                "date_to": "2026-01-31",
            },
        )
        assert resp.status_code == 200
        # Table must still exist and still contain all 4 rows.
        conn = db_module.get_db()
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM expenses WHERE user_id = ?", (user_id,)
        ).fetchone()
        conn.close()
        assert row["n"] == 4, "expenses table must survive an injection attempt"

    def test_non_iso_format_date_falls_back(self, user_a):
        client, _ = user_a
        resp = client.get("/profile?date_from=01/01/2026&date_to=31/01/2026")
        assert resp.status_code == 200
        stats = parse_stats(html_of(resp))
        assert stats["total_spent"] == "PKR 2,533"


# --------------------------------------------------------------------- #
# Zero matching expenses
# --------------------------------------------------------------------- #

class TestEmptyResultRange:
    def test_range_with_no_matching_expenses(self, user_a):
        client, _ = user_a
        resp = client.get("/profile?date_from=2027-01-01&date_to=2027-01-31")
        assert resp.status_code == 200
        html = html_of(resp)
        stats = parse_stats(html)
        assert stats["total_spent"] == "PKR 0"
        assert stats["transaction_count"] == "0"
        assert stats["top_category"] == "—"
        assert len(parse_transaction_rows(html)) == 0
        assert len(parse_category_names(html)) == 0

    def test_user_with_no_expenses_at_all(self, client):
        register_and_login(client, "Empty User", "empty@example.com")
        resp = client.get("/profile")
        assert resp.status_code == 200
        html = html_of(resp)
        stats = parse_stats(html)
        assert stats["total_spent"] == "PKR 0"
        assert stats["transaction_count"] == "0"
        assert stats["top_category"] == "—"
        assert len(parse_transaction_rows(html)) == 0
        assert len(parse_category_names(html)) == 0


# --------------------------------------------------------------------- #
# Currency formatting
# --------------------------------------------------------------------- #

class TestCurrencyFormatting:
    def test_currency_uses_pkr_prefix_with_thousands_separator(self, user_a):
        client, _ = user_a
        resp = client.get("/profile")
        html = html_of(resp)
        assert "PKR 2,533" in html
        assert "₹" not in html, "App must never render the Rupee sign"

    def test_zero_total_formatted_as_pkr_zero(self, user_a):
        client, _ = user_a
        resp = client.get("/profile?date_from=2027-01-01&date_to=2027-01-31")
        html = html_of(resp)
        assert "PKR 0" in html
        assert "₹" not in html


# --------------------------------------------------------------------- #
# Cross-user isolation
# --------------------------------------------------------------------- #

class TestCrossUserIsolation:
    def test_filtered_view_never_shows_another_users_expenses(self, app, user_a):
        client_a, user_a_id = user_a

        client_b = app.test_client()
        user_b_id = register_and_login(client_b, "User B", "userb@example.com")
        insert_expense(user_b_id, 777, "Health", "2026-01-01", "B-Jan1-Health")
        insert_expense(user_b_id, 222, "Food", "2026-01-20", "B-Jan20-Food")

        resp_a = client_a.get("/profile?date_from=2026-01-01&date_to=2026-01-31")
        html_a = html_of(resp_a)
        stats_a = parse_stats(html_a)
        assert stats_a["total_spent"] == "PKR 1,534", "User A's filtered total must be unaffected by User B's data"
        assert "B-Jan1-Health" not in html_a
        assert "B-Jan20-Food" not in html_a

        resp_b = client_b.get("/profile?date_from=2026-01-01&date_to=2026-01-31")
        html_b = html_of(resp_b)
        stats_b = parse_stats(html_b)
        assert stats_b["total_spent"] == "PKR 999"
        assert stats_b["transaction_count"] == "2"
        assert "A-Jan1-Food" not in html_b
        assert "A-Jan15-Transport" not in html_b
        assert "A-Jan31-Bills" not in html_b


# --------------------------------------------------------------------- #
# Filter UI markers
# --------------------------------------------------------------------- #

class TestFilterUIMarkers:
    def test_filter_bar_and_preset_chips_present(self, user_a):
        client, _ = user_a
        resp = client.get("/profile")
        html = html_of(resp)
        assert "filter-bar" in html
        assert "filter-chip" in html
        assert "This Month" in html
        assert "Last 3 Months" in html
        assert "Last 6 Months" in html
        assert "All Time" in html

    def test_custom_range_form_present(self, user_a):
        client, _ = user_a
        resp = client.get("/profile")
        html = html_of(resp)
        assert 'method="get"' in html.lower()
        assert 'name="date_from"' in html
        assert 'name="date_to"' in html
        assert html.count('type="date"') >= 2

    def test_custom_range_inputs_retain_submitted_values(self, user_a):
        client, _ = user_a
        resp = client.get("/profile?date_from=2026-01-01&date_to=2026-01-31")
        html = html_of(resp)
        assert 'value="2026-01-01"' in html
        assert 'value="2026-01-31"' in html
