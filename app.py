from flask import Flask, render_template, request, redirect, session
from database import get_db, init_db

app = Flask(__name__)
app.secret_key = "supersecret123"

ADMIN_PASSWORD = "admin123"

init_db()

# ---------------- SIGNUP ----------------
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        name = request.form["name"]
        email = request.form["email"]
        group = request.form["group"]

        conn = get_db()
        conn.execute(
            "INSERT INTO users (name,email,timetable_group) VALUES (?,?,?)",
            (name, email, group)
        )
        conn.commit()

        return "Added successfully!"

    return render_template("signup.html")


# ---------------- ADMIN LOGIN ----------------
@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        if request.form["password"] == ADMIN_PASSWORD:
            session["admin"] = True
            return redirect("/dashboard")

    return render_template("admin.html")


# ---------------- DASHBOARD ----------------
@app.route("/dashboard")
def dashboard():
    if not session.get("admin"):
        return redirect("/admin")

    conn = get_db()
    users = conn.execute("SELECT * FROM users").fetchall()
    week = conn.execute("SELECT value FROM settings WHERE key='week_type'").fetchone()[0]

    return render_template("dashboard.html", users=users, week=week)


# ---------------- SET WEEK ----------------
@app.route("/set-week/<w>")
def set_week(w):
    conn = get_db()
    conn.execute("UPDATE settings SET value=? WHERE key='week_type'", (w,))
    conn.commit()
    return redirect("/dashboard")


# ---------------- SEND TEST ----------------
@app.route("/send-test")
def send_test():
    import sender
    sender.send_all(test=True)
    return "Test emails sent"


app.run(host="0.0.0.0", port=5000)
