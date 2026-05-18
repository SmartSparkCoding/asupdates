from flask import Flask, render_template, request, redirect, session
from config import SECRET_KEY, ADMIN_PASSWORD
from db import init_db, get_db
from scheduler import start_scheduler

app = Flask(__name__)
app.secret_key = SECRET_KEY

init_db()
start_scheduler()


# ---------------- HOME ----------------
@app.route("/")
def home():
    return redirect("/signup")


# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email")
        pin = request.form.get("pin")

        db = get_db()
        c = db.cursor()

        try:
            c.execute(
                "INSERT INTO users (email, pin) VALUES (?, ?)",
                (email, pin),
            )
            db.commit()
        except Exception as e:
            return f"Error: {e}"

        db.close()
        return "User created successfully"

    return render_template("signup.html")


# ---------------- LOGIN ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE email=?",
            (email,),
        ).fetchone()
        db.close()

        if user:
            session["user"] = email
            return redirect("/dashboard")

        return "User not found"

    return render_template("login.html")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if not session.get("user"):
        return redirect("/login")

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE email=?",
        (session["user"],),
    ).fetchone()
    db.close()

    return render_template("dashboard.html", user=user)


# ---------------- ADMIN LOGIN ----------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin/dashboard")

        return "Wrong password"

    return render_template("admin.html")


# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin/dashboard")
def admin_dashboard():
    if not session.get("admin"):
        return redirect("/admin")

    db = get_db()
    users = db.execute("SELECT * FROM users").fetchall()
    settings = db.execute("SELECT * FROM settings WHERE id=1").fetchone()
    db.close()

    return render_template("admin_dashboard.html", users=users, settings=settings)


# ---------------- DELETE USER ----------------
@app.route("/admin/delete/<int:user_id>")
def delete_user(user_id):
    if not session.get("admin"):
        return redirect("/admin")

    db = get_db()
    db.execute("DELETE FROM users WHERE id=?", (user_id,))
    db.commit()
    db.close()

    return redirect("/admin/dashboard")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
