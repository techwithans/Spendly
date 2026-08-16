import os
import sqlite3
from datetime import datetime

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database.db import get_db, init_db, seed_db

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

    conn = get_db()

    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        conn.close()
        error = "An account with this email already exists."
        return render_template("register.html", error=error, name=name, email=email)

    password_hash = generate_password_hash(password)

    try:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, password_hash),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        error = "An account with this email already exists."
        return render_template("register.html", error=error, name=name, email=email)

    conn.close()
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))

    if request.method != "POST":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    conn = get_db()
    user = conn.execute("SELECT id, name, password_hash FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()

    if not user or not check_password_hash(user["password_hash"], password):
        error = "Invalid email or password."
        return render_template("login.html", error=error, email=email)

    session["user_id"] = user["id"]
    session["name"] = user["name"]
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

def _get_profile_user(conn, user_id):
    """User info card: name, email, member_since, initials."""
    row = conn.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    initials = "".join(part[0].upper() for part in row["name"].split()[:2])
    created = datetime.strptime(row["created_at"][:10], "%Y-%m-%d")
    return {
        "name": row["name"],
        "email": row["email"],
        "member_since": created.strftime("%B %Y"),
        "initials": initials,
    }


def _get_profile_transactions(conn, user_id):
    """Subagent 1: most recent transactions for the profile table.

    Return a list of dicts shaped like:
        {"date": "Aug 12", "description": "...", "category": "Food", "amount": "PKR 850"}
    ordered most-recent-first, limited to a small fixed count (e.g. 5).
    See .claude/specs/05-profile-backend-routes.md for the full contract.
    """
    rows = conn.execute(
        "SELECT date, description, category, amount FROM expenses "
        "WHERE user_id = ? ORDER BY date DESC, id DESC LIMIT 5",
        (user_id,),
    ).fetchall()

    transactions = []
    for row in rows:
        d = datetime.strptime(row["date"], "%Y-%m-%d")
        formatted_date = f"{d.strftime('%b')} {d.day}"
        transactions.append(
            {
                "date": formatted_date,
                "description": row["description"],
                "category": row["category"],
                "amount": "PKR {:,.0f}".format(row["amount"]),
            }
        )

    return transactions


def _get_profile_stats(conn, user_id):
    """Subagent 2: summary stats row (total_spent, transaction_count, top_category).

    Return a dict shaped like:
        {"total_spent": "PKR 18,240", "transaction_count": 34, "top_category": "Food"}
    Must handle the zero-expenses case without raising.
    See .claude/specs/05-profile-backend-routes.md for the full contract.
    """
    total_row = conn.execute(
        "SELECT SUM(amount) AS total FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    total = total_row["total"] if total_row["total"] is not None else 0
    total_spent = "PKR {:,.0f}".format(total)

    count_row = conn.execute(
        "SELECT COUNT(*) AS n FROM expenses WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    transaction_count = count_row["n"]

    top_row = conn.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "WHERE user_id = ? GROUP BY category ORDER BY total DESC LIMIT 1",
        (user_id,),
    ).fetchone()
    top_category = top_row["category"] if top_row is not None else "—"

    return {
        "total_spent": total_spent,
        "transaction_count": transaction_count,
        "top_category": top_category,
    }


def _get_profile_categories(conn, user_id):
    """Subagent 3: per-category breakdown rows.

    Return a list of dicts shaped like:
        {"name": "Food", "amount": "PKR 6,540", "bar_class": "bar-w-78"}
    one per category the user has spent in. `bar_class` must be one of the
    existing CSS classes in static/css/style.css (bar-w-18/30/42/60/78) —
    pick the nearest one to that category's percentage share of total spend.
    See .claude/specs/05-profile-backend-routes.md for the full contract.
    """
    rows = conn.execute(
        "SELECT category, SUM(amount) AS total FROM expenses "
        "WHERE user_id = ? GROUP BY category ORDER BY total DESC",
        (user_id,),
    ).fetchall()

    grand_total = sum(row["total"] for row in rows)

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
    for row in rows:
        total = row["total"]
        pct = (total / grand_total * 100) if grand_total else 0
        categories.append(
            {
                "name": row["category"],
                "amount": "PKR {:,.0f}".format(total),
                "bar_class": _nearest_bar_class(pct),
            }
        )

    return categories


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user_id = session["user_id"]
    conn = get_db()

    user = _get_profile_user(conn, user_id)
    stats = _get_profile_stats(conn, user_id)
    transactions = _get_profile_transactions(conn, user_id)
    categories = _get_profile_categories(conn, user_id)

    conn.close()

    return render_template(
        "profile.html",
        user=user,
        stats=stats,
        transactions=transactions,
        categories=categories,
    )


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    with app.app_context():
        init_db()
        seed_db()
    app.run(debug=True, port=5001)
