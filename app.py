import os
import sqlite3

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


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    user = {
        "name": "Demo User",
        "email": "demo@spendly.com",
        "member_since": "August 2026",
        "initials": "DU",
    }
    stats = {
        "total_spent": "PKR 18,240",
        "transaction_count": 34,
        "top_category": "Food",
    }
    transactions = [
        {"date": "Aug 12", "description": "Weekly grocery shopping", "category": "Food", "amount": "PKR 850"},
        {"date": "Aug 10", "description": "Uber ride to office", "category": "Transport", "amount": "PKR 350"},
        {"date": "Aug 8", "description": "Electricity bill", "category": "Bills", "amount": "PKR 4,500"},
        {"date": "Aug 6", "description": "Pharmacy - medicines", "category": "Health", "amount": "PKR 1,200"},
        {"date": "Aug 4", "description": "New shoes", "category": "Shopping", "amount": "PKR 3,200"},
    ]
    categories = [
        {"name": "Food", "amount": "PKR 6,540", "bar_class": "bar-w-78"},
        {"name": "Bills", "amount": "PKR 5,020", "bar_class": "bar-w-60"},
        {"name": "Shopping", "amount": "PKR 3,540", "bar_class": "bar-w-42"},
        {"name": "Health", "amount": "PKR 2,540", "bar_class": "bar-w-30"},
        {"name": "Transport", "amount": "PKR 1,600", "bar_class": "bar-w-18"},
    ]

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
