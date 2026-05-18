from flask import Flask, render_template, request, redirect, session, url_for, flash
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = "CHANGE_THIS_TO_A_RANDOM_SECRET"

DB_PATH = "database.db"

# ----------------------------
# DATABASE CONNECTION
# ----------------------------
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ----------------------------
# AUTH DECORATORS
# ----------------------------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper


# ----------------------------
# HOME REDIRECT
# ----------------------------
@app.route("/")
def home():
    return redirect("/login")


# ----------------------------
# SIGNUP
# ----------------------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        pin = request.form.get("pin")

        conn = db()
        c = conn.cursor()

        c.execute("SELECT * FROM users WHERE email=?", (email,))
        if c.fetchone():
            flash("User already exists")
            return redirect("/signup")

        pin_hash = generate_password_hash(pin) if pin else None

        c.execute("""
            INSERT INTO users (email, pin_hash, is_admin, send_emails)
            VALUES (?, ?, 0, 1)
        """, (email, pin_hash))

        conn.commit()
        conn.close()

        flash("Account created. Please log in.")
        return redirect("/login")

    return render_template("signup.html")


# ----------------------------
# LOGIN (STEP 1: EMAIL)
# ----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]

        conn = db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email=?", (email,))
        user = c.fetchone()
        conn.close()

        if not user:
            flash("User not found")
            return redirect("/login")

        session["temp_user"] = user["id"]

        # if no PIN -> login directly
        if not user["pin_hash"]:
            session["user_id"] = user["id"]
            session["is_admin"] = user["is_admin"]
            return redirect("/dashboard")

        return redirect("/pin")

    return render_template("login.html")


# ----------------------------
# PIN STEP
# ----------------------------
@app.route("/pin", methods=["GET", "POST"])
def pin():
    user_id = session.get("temp_user")

    if not user_id:
        return redirect("/login")

    if request.method == "POST":
        pin = request.form["pin"]

        conn = db()
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id=?", (user_id,))
        user = c.fetchone()
        conn.close()

        if not user or not check_password_hash(user["pin_hash"], pin):
            return render_template("pin.html", error="Incorrect PIN")

        session["user_id"] = user["id"]
        session["is_admin"] = user["is_admin"]
        session.pop("temp_user", None)

        return redirect("/dashboard")

    return render_template("pin.html")


# ----------------------------
# DASHBOARD
# ----------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    conn = db()
    c = conn.cursor()

    c.execute("SELECT email FROM users WHERE id=?", (session["user_id"],))
    user = c.fetchone()

    return render_template("dashboard.html", email=user["email"])


# ----------------------------
# ADMIN DASHBOARD
# ----------------------------
@app.route("/admin")
@admin_required
def admin():
    conn = db()
    c = conn.cursor()

    c.execute("SELECT id, email, send_emails FROM users")
    users = c.fetchall()

    return render_template("admin.html", users=users)


# ----------------------------
# DELETE USER
# ----------------------------
@app.route("/delete-user/<int:user_id>")
@admin_required
def delete_user(user_id):
    conn = db()
    c = conn.cursor()

    c.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
    conn.close()

    return redirect("/admin")


# ----------------------------
# TOGGLE EMAILS
# ----------------------------
@app.route("/toggle-emails", methods=["POST"])
@login_required
def toggle_emails():
    conn = db()
    c = conn.cursor()

    c.execute("SELECT send_emails FROM users WHERE id=?", (session["user_id"],))
    current = c.fetchone()["send_emails"]

    c.execute("""
        UPDATE users
        SET send_emails=?
        WHERE id=?
    """, (0 if current else 1, session["user_id"]))

    conn.commit()
    conn.close()

    return redirect("/dashboard")


# ----------------------------
# LOGOUT (FIXED)
# ----------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ----------------------------
# HOLIDAY CHECK (UTILITY)
# ----------------------------
def is_holiday(date_str):
    conn = db()
    c = conn.cursor()

    c.execute("SELECT 1 FROM holidays WHERE date=?", (date_str,))
    result = c.fetchone()

    conn.close()
    return result is not None


# ----------------------------
# ERROR HANDLERS
# ----------------------------
@app.errorhandler(404)
def not_found(e):
    return render_template("error.html", msg="Page not found"), 404


@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", msg="Server error"), 500


# ----------------------------
# RUN SERVER
# ----------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
