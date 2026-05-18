from apscheduler.schedulers.background import BackgroundScheduler
from db import get_db
from emailer import send_email

def job():
    db = get_db()
    c = db.cursor()

    holiday = c.execute("SELECT holiday_mode FROM settings WHERE id=1").fetchone()[0]

    if holiday == 1:
        print("Holiday mode ON")
        return

    users = c.execute("SELECT email, send_emails FROM users").fetchall()

    for u in users:
        if u["send_emails"] == 1:
            html = "<h2>Daily School Update</h2><p>Your timetable here</p>"
            send_email(u["email"], "Daily Update", html)

    db.close()

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(job, "cron", hour=8, minute=0)
    scheduler.start()
