import sqlite3
import datetime

def get_db():
    return sqlite3.connect("data.db")

def should_skip():
    today = datetime.date.today().isoformat()

    # skip weekends
    if datetime.datetime.today().weekday() >= 5:
        return True

    conn = get_db()
    if conn.execute("SELECT * FROM skip_dates WHERE date=?", (today,)).fetchone():
        return True

    return False

def send_email(email, html):
    # TEMP (prints instead of sending)
    print(f"Sending to {email}")
    print(html)

def generate_email(name):
    # 🔥 THIS IS WHERE YOUR BEEFREE TEMPLATE GOES
    return f"""
    <html>
    <body>
        <h1>Hello {name}</h1>
        <p>Your Ashford update is ready.</p>
    </body>
    </html>
    """

def send_all(test=False):
    if not test and should_skip():
        return

    conn = get_db()
    users = conn.execute("SELECT * FROM users").fetchall()

    for u in users:
        name = u[1]
        email = u[2]

        html = generate_email(name)
        send_email(email, html)

if __name__ == "__main__":
    send_all()
