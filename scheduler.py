from apscheduler.schedulers.background import BackgroundScheduler
from db import get_db
from emailer import send_email


def send_daily_emails():
    db = get_db()
    c = db.cursor()

    settings = c.execute("SELECT * FROM settings WHERE id=1").fetchone()
    holiday_mode = settings[2]

    if holiday_mode == 1:
        print("Holiday mode ON - skipping emails")
        return

    users = c.execute("SELECT email, send_emails FROM users").fetchall()

    for email, send in users:
        if send == 1:
            html = "<h1>Daily Update</h1><p>Your timetable goes here</p>"
            send_email(email, "Daily School Update", html)

    db.close()


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_daily_emails, "cron", hour=8, minute=0)
    scheduler.start()
