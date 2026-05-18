from flask import Flask, render_template, request, redirect, session
from config import SECRET_KEY, ADMIN_PASSWORD
from db import init_db, get_db
from scheduler import start_scheduler

app = Flask(__name__)
app.secret_key = SECRET_KEY

init_db()
start_scheduler()

# HOME
@app.route("/")
def home():
    return redirect("/login")

# SIGNUP
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form.get("email")
        pin = request.form.get("pin")

        db = get_db()
        db.execute("INSERT INTO users (email, pin) VALUES (?, ?)", (email, pin))
        db.commit()
        db.close()

        return redirect("/login")

    return render_template("signup.html")

# LOGIN STEP 1 (EMAIL)
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        db.close()

        if not user:
            return "User not found"

        session["temp_email"] = email

        # if PIN exists → go PIN page
        if user["pin"]:
            return redirect("/pin")

        session["user"] = email
        return redirect("/dashboard")

    return render_template("login.html")

# PIN CHECK
@app.route("/pin", methods=["GET", "POST"])
def pin():
    email = session.get("temp_email")

    if not email:
        return redirect("/login")

    if request.method == "POST":
        entered = request.form.get("pin")

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        db.close()

        if user["pin"] == entered:
            session["user"] = email
            return redirect("/dashboard")

        return "Wrong PIN"

    return render_template("pin.html")

# DASHBOARD
@app.route("/dashboard")
def dashboard():
    if not session.get("user"):
        return redirect("/login")

    return render_template("dashboard.html", email=session["user"])

# ADMIN
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form.get("password") == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/admin/dashboard")

        return "Wrong password"

    return render_template("admin.html")

# ADMIN DASH
@app.route("/admin/dashboard")
def admin_dash():
    if not session.get("admin"):
        return redirect("/admin")

    db = get_db()
    users = db.execute("SELECT * FROM users").fetchall()
    db.close()

    return render_template("admin_dashboard.html", users=users)

# DELETE USER
@app.route("/admin/delete/<int:id>")
def delete(id):
    if not session.get("admin"):
        return redirect("/admin")

    db = get_db()
    db.execute("DELETE FROM users WHERE id=?", (id,))
    db.commit()
    db.close()

    return redirect("/admin/dashboard")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
