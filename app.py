import calendar
import math
import os
from datetime import date, datetime

from flask import Flask, abort, redirect, render_template, request, session, url_for
from postgrest import APIError
from supabase_auth.errors import AuthApiError

from database.db import CATEGORIES, get_auth_client, get_client, get_db, init_db, seed_db

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method != "POST":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    if not name or not email or not password or not confirm_password:
        error = "All fields are required."
        return render_template("register.html", error=error, name=name, email=email)

    if "@" not in email:
        error = "Enter a valid email address."
        return render_template("register.html", error=error, name=name, email=email)

    if password != confirm_password:
        error = "Passwords do not match."
        return render_template("register.html", error=error, name=name, email=email)

    if len(password) < 8:
        error = "Password must be at least 8 characters."
        return render_template("register.html", error=error, name=name, email=email)

    supabase = get_client()

    existing = supabase.table("users").select("id").eq("email", email).execute().data
    if existing:
        error = "An account with this email already exists."
        return render_template("register.html", error=error, name=name, email=email)

    auth_client = get_auth_client()
    try:
        response = auth_client.auth.sign_up({
            "email": email,
            "password": password,
            "options": {"data": {"name": name}},
        })
    except AuthApiError as e:
        if e.code in ("email_exists", "user_already_exists"):
            error = "An account with this email already exists."
            return render_template("register.html", error=error, name=name, email=email)
        raise

    user_id = response.user.id
    try:
        supabase.table("users").insert(
            {"id": user_id, "name": name, "email": email}
        ).execute()
    except APIError as e:
        if e.code == "23505":
            error = "An account with this email already exists."
            return render_template("register.html", error=error, name=name, email=email)
        raise

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method != "POST":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    auth_client = get_auth_client()
    try:
        response = auth_client.auth.sign_in_with_password({"email": email, "password": password})
    except AuthApiError as e:
        if e.code in ("invalid_credentials", "email_not_confirmed"):
            error = "Invalid email or password."
            return render_template("login.html", error=error, email=email)
        raise

    user_id = response.user.id
    name_row = get_client().table("users").select("name").eq("id", user_id).execute().data[0]
    session["user_id"] = user_id
    session["name"] = name_row["name"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Profile data helpers (see .claude/specs/05-profile-backend-routes.md) #
# ------------------------------------------------------------------ #

def _shift_months(d, months):
    """Shift `d` back by `months` calendar months, clamping the day of
    month to the shifted month's length (e.g. Aug 31 - 6mo -> Feb 28/29)."""
    month_index = d.month - 1 - months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(d.day, last_day)
    return date(year, month, day)


def _profile_presets():
    """Quick-select date ranges for the profile filter bar, anchored on today."""
    today = date.today()
    return {
        "month": (today.replace(day=1).isoformat(), today.isoformat()),
        "3months": (_shift_months(today, 3).isoformat(), today.isoformat()),
        "6months": (_shift_months(today, 6).isoformat(), today.isoformat()),
    }


def _resolve_date_filter(args, presets):
    """Validate date_from/date_to query args into a filter dict.

    Any missing, malformed, or inverted (start > end) range silently falls
    back to the unfiltered "all" state rather than raising or erroring —
    this app has no flash-message convention to surface such errors with.
    """
    date_from = (args.get("date_from") or "").strip()
    date_to = (args.get("date_to") or "").strip()

    if not date_from or not date_to:
        return {"start": None, "end": None, "active": "all"}

    try:
        parsed_from = datetime.strptime(date_from, "%Y-%m-%d").date()
        parsed_to = datetime.strptime(date_to, "%Y-%m-%d").date()
    except ValueError:
        return {"start": None, "end": None, "active": "all"}

    if parsed_from > parsed_to:
        return {"start": None, "end": None, "active": "all"}

    start, end = parsed_from.isoformat(), parsed_to.isoformat()

    active = "custom"
    for name, bounds in presets.items():
        if (start, end) == bounds:
            active = name
            break

    return {"start": start, "end": end, "active": active}


def _apply_date_filter(query, start_date, end_date):
    """Narrow an expenses query to an inclusive date range, if both bounds are given."""
    if start_date and end_date:
        return query.gte("date", start_date).lte("date", end_date)
    return query


def _get_profile_user(supabase, user_id):
    """User info card: name, email, member_since, initials."""
    response = supabase.table("users").select("name, email, created_at").eq("id", user_id).execute()
    row = response.data[0]
    initials = "".join(part[0].upper() for part in row["name"].split()[:2])
    created = datetime.strptime(row["created_at"][:10], "%Y-%m-%d")
    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": created.strftime("%B %Y"),
        "initials": initials,
    }


def _get_profile_transactions(supabase, user_id, start_date=None, end_date=None):
    """Subagent 1: most recent transactions for the profile table.

    Return a list of dicts shaped like:
        {"date": "Aug 12", "description": "...", "category": "Food", "amount": "PKR 850"}
    ordered most-recent-first, limited to a small fixed count (e.g. 5).
    See .claude/specs/05-profile-backend-routes.md for the full contract.
    """
    query = supabase.table("expenses").select("id, date, description, category, amount").eq("user_id", user_id)
    query = _apply_date_filter(query, start_date, end_date)
    rows = query.order("date", desc=True).order("id", desc=True).limit(5).execute().data

    transactions = []
    for row in rows:
        d = datetime.strptime(row["date"], "%Y-%m-%d")
        formatted_date = f"{d.strftime('%b')} {d.day}"
        transactions.append(
            {
                "id": row["id"],
                "date": formatted_date,
                "description": row["description"],
                "category": row["category"],
                "amount": "PKR {:,.0f}".format(row["amount"]),
            }
        )

    return transactions


def _get_profile_stats(supabase, user_id, start_date=None, end_date=None):
    """Subagent 2: summary stats row (total_spent, transaction_count, top_category).

    Return a dict shaped like:
        {"total_spent": "PKR 18,240", "transaction_count": 34, "top_category": "Food"}
    Must handle the zero-expenses case without raising.
    See .claude/specs/05-profile-backend-routes.md for the full contract.

    PostgREST can do SUM/GROUP BY via embedded aggregate syntax, but only
    after a non-default per-project Postgres role setting is enabled — so
    aggregation is done client-side here instead, over the fetched rows.
    """
    query = supabase.table("expenses").select("amount, category").eq("user_id", user_id)
    query = _apply_date_filter(query, start_date, end_date)
    rows = query.execute().data

    total = sum(row["amount"] for row in rows)
    total_spent = "PKR {:,.0f}".format(total)
    transaction_count = len(rows)

    category_totals = {}
    for row in rows:
        category_totals[row["category"]] = category_totals.get(row["category"], 0) + row["amount"]
    top_category = max(category_totals, key=category_totals.get) if category_totals else "—"

    return {
        "total_spent": total_spent,
        "transaction_count": transaction_count,
        "top_category": top_category,
    }


def _get_profile_categories(supabase, user_id, start_date=None, end_date=None):
    """Subagent 3: per-category breakdown rows.

    Return a list of dicts shaped like:
        {"name": "Food", "amount": "PKR 6,540", "bar_class": "bar-w-78"}
    one per category the user has spent in. `bar_class` must be one of the
    existing CSS classes in static/css/style.css (bar-w-18/30/42/60/78) —
    pick the nearest one to that category's percentage share of total spend.
    See .claude/specs/05-profile-backend-routes.md for the full contract.
    """
    query = supabase.table("expenses").select("amount, category").eq("user_id", user_id)
    query = _apply_date_filter(query, start_date, end_date)
    rows = query.execute().data

    category_totals = {}
    for row in rows:
        category_totals[row["category"]] = category_totals.get(row["category"], 0) + row["amount"]

    grand_total = sum(category_totals.values())

    bar_classes = [
        (18, "bar-w-18"),
        (30, "bar-w-30"),
        (42, "bar-w-42"),
        (60, "bar-w-60"),
        (78, "bar-w-78"),
    ]

    def _nearest_bar_class(pct):
        return min(bar_classes, key=lambda pair: abs(pair[0] - pct))[1]

    categories = []
    for category, total in sorted(category_totals.items(), key=lambda kv: kv[1], reverse=True):
        pct = (total / grand_total * 100) if grand_total else 0
        categories.append(
            {
                "name": category,
                "amount": "PKR {:,.0f}".format(total),
                "bar_class": _nearest_bar_class(pct),
            }
        )

    return categories


# ------------------------------------------------------------------ #
# Analytics data helpers (see .claude/specs/11-analytics-page.md)     #
# ------------------------------------------------------------------ #

def _nearest_height_class(pct):
    """Snap a 0-100 percentage to the nearest `bar-h-<n>` class (steps of 5)."""
    n = max(0, min(100, int(round(pct / 5.0)) * 5))
    return f"bar-h-{n}"


def _analytics_summary(rows):
    """Headline stat row: total spend, transaction count, mean per
    transaction, and mean per calendar month that has any spend."""
    total = sum(row["amount"] for row in rows)
    count = len(rows)
    months = {row["date"][:7] for row in rows}

    avg_transaction = total / count if count else 0
    avg_monthly = total / len(months) if months else 0

    return {
        "total_spent": "PKR {:,.0f}".format(total),
        "transaction_count": count,
        "avg_transaction": "PKR {:,.0f}".format(avg_transaction),
        "avg_monthly": "PKR {:,.0f}".format(avg_monthly),
    }


def _analytics_monthly(rows):
    """Last 6 calendar months (oldest first, current month last), each with
    its formatted total and a `bar-h-<n>` class sized against the tallest
    month in the window."""
    today = date.today()
    buckets = []
    for offset in range(5, -1, -1):
        month = _shift_months(today, offset)
        buckets.append({"key": month.strftime("%Y-%m"), "label": month.strftime("%b"), "total": 0.0})

    by_key = {bucket["key"]: bucket for bucket in buckets}
    for row in rows:
        bucket = by_key.get(row["date"][:7])
        if bucket is not None:
            bucket["total"] += row["amount"]

    peak = max((bucket["total"] for bucket in buckets), default=0)

    return [
        {
            "label": bucket["label"],
            "amount": "PKR {:,.0f}".format(bucket["total"]),
            "bar_class": _nearest_height_class(bucket["total"] / peak * 100 if peak else 0),
        }
        for bucket in buckets
    ]


def _analytics_month_comparison(rows):
    """This month's total vs last month's, with an integer percentage change
    and an up/down/flat trend flag. `change_pct` is 0 when last month had no
    spend (no meaningful ratio)."""
    today = date.today()
    this_key = today.strftime("%Y-%m")
    last_key = _shift_months(today, 1).strftime("%Y-%m")

    this_total = sum(row["amount"] for row in rows if row["date"][:7] == this_key)
    last_total = sum(row["amount"] for row in rows if row["date"][:7] == last_key)

    if last_total:
        change_pct = int(round(abs(this_total - last_total) / last_total * 100))
    else:
        change_pct = 0

    if this_total > last_total:
        trend = "up"
    elif this_total < last_total:
        trend = "down"
    else:
        trend = "flat"

    return {
        "this_month": "PKR {:,.0f}".format(this_total),
        "last_month": "PKR {:,.0f}".format(last_total),
        "change_pct": change_pct,
        "trend": trend,
    }


def _analytics_biggest(rows):
    """The user's single largest expense, or None if they have none."""
    if not rows:
        return None

    row = max(rows, key=lambda r: r["amount"])
    d = datetime.strptime(row["date"], "%Y-%m-%d")
    return {
        "amount": "PKR {:,.0f}".format(row["amount"]),
        "category": row["category"],
        "description": row["description"] or "—",
        "date": f"{d.strftime('%b')} {d.day}",
    }


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    presets = _profile_presets()
    date_filter = _resolve_date_filter(request.args, presets)

    supabase = get_client()

    user = _get_profile_user(supabase, user_id)
    stats = _get_profile_stats(supabase, user_id, date_filter["start"], date_filter["end"])
    transactions = _get_profile_transactions(supabase, user_id, date_filter["start"], date_filter["end"])
    categories = _get_profile_categories(supabase, user_id, date_filter["start"], date_filter["end"])

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
        date_filter=date_filter,
        presets=presets,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    supabase = get_client()

    rows = (
        supabase.table("expenses")
        .select("amount, category, date, description")
        .eq("user_id", user_id)
        .execute()
        .data
    )

    return render_template(
        "analytics.html",
        has_data=bool(rows),
        summary=_analytics_summary(rows),
        monthly=_analytics_monthly(rows),
        categories=_get_profile_categories(supabase, user_id),
        comparison=_analytics_month_comparison(rows),
        biggest=_analytics_biggest(rows),
    )


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    today = date.today().isoformat()

    if request.method != "POST":
        return render_template(
            "add_expense.html",
            categories=CATEGORIES,
            today=today,
            amount="",
            category="",
            date=today,
            description="",
        )

    amount = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    expense_date = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()

    def _rerender(error):
        return render_template(
            "add_expense.html",
            error=error,
            categories=CATEGORIES,
            today=today,
            amount=amount,
            category=category,
            date=expense_date,
            description=description,
        )

    try:
        amount_value = float(amount)
    except ValueError:
        return _rerender("Enter a valid amount.")

    if not math.isfinite(amount_value) or amount_value <= 0:
        return _rerender("Amount must be a positive number.")

    if category not in CATEGORIES:
        return _rerender("Select a valid category.")

    try:
        parsed_date = datetime.strptime(expense_date, "%Y-%m-%d").date()
    except ValueError:
        return _rerender("Enter a valid date.")

    if parsed_date > date.today():
        return _rerender("Date cannot be in the future.")

    supabase = get_client()
    supabase.table("expenses").insert(
        {
            "user_id": session["user_id"],
            "amount": amount_value,
            "category": category,
            "date": expense_date,
            "description": description or None,
        }
    ).execute()

    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    supabase = get_client()
    response = (
        supabase.table("expenses")
        .select("id, amount, category, date, description")
        .eq("id", id)
        .eq("user_id", session["user_id"])
        .execute()
    )
    expense = response.data[0] if response.data else None

    if expense is None:
        abort(404)

    today = date.today().isoformat()

    if request.method != "POST":
        return render_template(
            "edit_expense.html",
            expense_id=id,
            categories=CATEGORIES,
            today=today,
            amount=expense["amount"],
            category=expense["category"],
            date=expense["date"],
            description=expense["description"] or "",
        )

    amount = request.form.get("amount", "").strip()
    category = request.form.get("category", "").strip()
    expense_date = request.form.get("date", "").strip()
    description = request.form.get("description", "").strip()

    def _rerender(error):
        return render_template(
            "edit_expense.html",
            error=error,
            expense_id=id,
            categories=CATEGORIES,
            today=today,
            amount=amount,
            category=category,
            date=expense_date,
            description=description,
        )

    try:
        amount_value = float(amount)
    except ValueError:
        return _rerender("Enter a valid amount.")

    if not math.isfinite(amount_value) or amount_value <= 0:
        return _rerender("Amount must be a positive number.")

    if category not in CATEGORIES:
        return _rerender("Select a valid category.")

    try:
        parsed_date = datetime.strptime(expense_date, "%Y-%m-%d").date()
    except ValueError:
        return _rerender("Enter a valid date.")

    if parsed_date > date.today():
        return _rerender("Date cannot be in the future.")

    supabase.table("expenses").update(
        {
            "amount": amount_value,
            "category": category,
            "date": expense_date,
            "description": description or None,
        }
    ).eq("id", id).eq("user_id", session["user_id"]).execute()

    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/delete", methods=["POST"])
def delete_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    supabase = get_client()
    response = (
        supabase.table("expenses")
        .delete()
        .eq("id", id)
        .eq("user_id", session["user_id"])
        .execute()
    )

    if not response.data:
        abort(404)

    return redirect(url_for("profile"))


if __name__ == "__main__":
    with app.app_context():
        init_db()
        seed_db()
    port = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("PORT") is None
    app.run(host="0.0.0.0", port=port, debug=debug)
