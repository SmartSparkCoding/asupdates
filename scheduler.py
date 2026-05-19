from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz
from db import get_db
from emailer import send_email
from email_templates import parse_timetable, render_email_html, timetable_rows
from config import TIMEZONE, SCHEDULER_ENABLED


def _row_to_dict(row):
    if not row:
        return {}
    return {key: row[key] for key in row.keys()}


def _settings_defaults(settings):
    settings = settings or {}
    return {
        "holiday_mode": settings.get("holiday_mode", 0),
        "holiday_weeks": settings.get("holiday_weeks", 0),
        "ab_week": settings.get("ab_week", "A"),
        "menu_week": settings.get("menu_week", 1),
        "menu_week_1": settings.get("menu_week_1", ""),
        "menu_week_2": settings.get("menu_week_2", ""),
        "menu_week_3": settings.get("menu_week_3", ""),
    }


def _build_email_context(user, settings):
    current_week = settings.get("ab_week", "A")
    timetable_raw = user.get("timetable_a", "") if current_week == "A" else user.get("timetable_b", "")
    timetable = parse_timetable(timetable_raw)
    menu_week = max(1, min(3, int(settings.get("menu_week", 1) or 1)))
    menu_text = settings.get(f"menu_week_{menu_week}", "")
    display_name = user.get("name") or user.get("email", "").split("@")[0].replace(".", " ").title() or "Student"

    return {
        "name": display_name,
        "current_date": datetime.now().strftime("%A, %d %B %Y"),
        "sent_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "timetable": timetable_rows(timetable),
        "timetable_label": f"Week {current_week}",
        "timetable_week": current_week,
        "lunch": menu_text,
        "menu_week": menu_week,
        "events": [
            f"Holiday mode: {'ON' if settings.get('holiday_mode') == 1 else 'OFF'}",
            f"Current rota week: {menu_week}",
        ],
        "updates": [
            f"Email updates are {'enabled' if user.get('send_emails', 1) == 1 else 'disabled'} for this account.",
            "Open the dashboard to update your timetable or account details.",
        ],
        "unsubscribe_url": "https://ashfordschool.co.uk",
    }


def generate_email_html(user_email):
    """Generate personalized email HTML for a specific user email."""

    db = get_db()
    c = db.cursor()
    c.execute("SELECT id, email, name, pin, send_emails, timetable_a, timetable_b, created_at FROM users WHERE email=?", (user_email,))
    user = _row_to_dict(c.fetchone())
    c.execute("SELECT id, holiday_mode, holiday_weeks, ab_week, menu_week, menu_week_1, menu_week_2, menu_week_3 FROM settings WHERE id=1")
    settings = _settings_defaults(_row_to_dict(c.fetchone()))
    db.close()

    if not user:
        return ""

    return render_email_html(_build_email_context(user, settings))


def send_daily_emails():
    """Send emails to all active users (weekdays only, not during holidays)."""
    
    try:
        # Check if today is a weekend
        today = datetime.now()
        if today.weekday() >= 5:  # 5=Saturday, 6=Sunday
            print(f"[ℹ] Skipping email send - it's {today.strftime('%A')}")
            return
        
        db = get_db()
        c = db.cursor()
        
        # Check holiday mode
        c.execute("SELECT holiday_mode FROM settings WHERE id=1")
        result = c.fetchone()
        holiday_mode = result[0] if result else 0
        
        if holiday_mode == 1:
            print("[ℹ] Holiday mode is ON - skipping emails")
            db.close()
            return
        
        # Get all users with send_emails enabled
        c.execute("SELECT id, email, name, pin, send_emails, timetable_a, timetable_b, created_at FROM users WHERE send_emails = 1")
        users = c.fetchall()
        c.execute("SELECT id, holiday_mode, holiday_weeks, ab_week, menu_week, menu_week_1, menu_week_2, menu_week_3 FROM settings WHERE id=1")
        settings = _settings_defaults(_row_to_dict(c.fetchone()))
        db.close()
        
        if not users:
            print("[ℹ] No users to send emails to")
            return
        
        # Send email to each user
        success_count = 0
        for user in users:
            user_record = _row_to_dict(user)
            email = user_record.get("email")
            html = render_email_html(_build_email_context(user_record, settings))
            
            if send_email(email, "AS Updates - Daily School Update", html):
                success_count += 1
        
        print(f"[✓] Sent emails to {success_count}/{len(users)} users")
        
    except Exception as e:
        print(f"[✗] Scheduler error: {e}")


def start_scheduler():
    """Start background scheduler for daily emails."""
    
    if not SCHEDULER_ENABLED:
        print("[ℹ] Scheduler disabled")
        return None
    
    try:
        scheduler = BackgroundScheduler()
        
        # Add job: every weekday at 08:00 UK time
        # Mon-Fri (0-4), at 08:00
        trigger = CronTrigger(
            day_of_week="mon-fri",
            hour=8,
            minute=0,
            timezone=TIMEZONE
        )
        
        scheduler.add_job(
            send_daily_emails,
            trigger=trigger,
            id='daily_email_job',
            name='Daily email sender',
            misfire_grace_time=600  # Allow up to 10 min late
        )
        
        scheduler.start()
        print(f"[✓] Scheduler started - emails at 08:00 {TIMEZONE}, Mon-Fri")
        return scheduler
        
    except Exception as e:
        print(f"[✗] Scheduler error: {e}")
        return None
