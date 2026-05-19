from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import json
from datetime import datetime
import pytz
from db import get_db
from emailer import send_email
from email_templates import (
    DAY_TIMETABLE_FIELDS,
    WEEKDAYS,
    parse_timetable,
    parse_week_menu,
    render_email_html,
    timetable_day_rows,
)
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
        "school_notice": settings.get("school_notice", ""),
    }


def _notice_lines(raw_notice):
    if not raw_notice:
        return []
    lines = [line.strip() for line in str(raw_notice).splitlines()]
    return [line for line in lines if line]


def _parse_day_timetable(raw_value):
    if not raw_value:
        return {day: {field: "" for field in DAY_TIMETABLE_FIELDS} for day in WEEKDAYS}

    if isinstance(raw_value, dict):
        result = {day: {field: "" for field in DAY_TIMETABLE_FIELDS} for day in WEEKDAYS}
        for day in WEEKDAYS:
            if day in raw_value and isinstance(raw_value[day], dict):
                for field in DAY_TIMETABLE_FIELDS:
                    result[day][field] = str(raw_value[day].get(field, "")).strip()
        return result

    try:
        parsed = json.loads(raw_value)
        return _parse_day_timetable(parsed)
    except (TypeError, ValueError):
        return {day: {field: "" for field in DAY_TIMETABLE_FIELDS} for day in WEEKDAYS}


def _parse_menu_data(menu_text):
    weekly_menu = parse_week_menu(menu_text)
    current_day = datetime.now().strftime("%A")
    if isinstance(weekly_menu, dict) and current_day in weekly_menu:
        return weekly_menu[current_day]

    return {
        "main": str(menu_text or "").strip(),
        "sides": "",
        "pasta_bar": "",
        "street_food": "",
        "potatoes": "",
        "soup": "",
        "vegetarian": "",
        "dessert": "",
    }


def _build_email_context(user, settings):
    current_week = settings.get("ab_week", "A")
    timetable_raw = user.get("timetable_a", "") if current_week == "A" else user.get("timetable_b", "")
    timetable = parse_timetable(timetable_raw)
    current_day = datetime.now().strftime("%A")
    day_schedule = {row["period"]: row for row in timetable_day_rows(timetable, current_day)} if current_day in WEEKDAYS else {}
    day_timetable = _parse_day_timetable(user.get("day_timetable", ""))
    current_day_timetable = day_timetable.get(current_day, {}) if current_day in WEEKDAYS else {}
    menu_week = max(1, min(3, int(settings.get("menu_week", 1) or 1)))
    menu_text = settings.get(f"menu_week_{menu_week}", "")
    menu_data = _parse_menu_data(menu_text)
    school_notice = settings.get("school_notice", "")
    display_name = user.get("name") or user.get("email", "").split("@")[0].replace(".", " ").title() or "Student"

    return {
        "name": display_name,
        "current_date": datetime.now().strftime("%A, %d %B %Y"),
        "sent_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "day_name": current_day,
        "day_schedule": day_schedule,
        "current_day_schedule": day_schedule,
        "current_day_timetable": current_day_timetable,
        "current_week_schedule": timetable_day_rows(timetable, current_day) if current_day in WEEKDAYS else [],
        "lunch": menu_data,
        "timetable_label": f"Week {current_week}",
        "timetable_week": current_week,
        "menu_week": menu_week,
        "events": [
            f"Holiday mode: {'ON' if settings.get('holiday_mode') == 1 else 'OFF'}",
            f"Current rota week: {menu_week}",
        ],
        "updates": [
            f"Email updates are {'enabled' if user.get('send_emails', 1) == 1 else 'disabled'} for this account.",
            "Open the dashboard to update your timetable or account details.",
        ],
        "school_notice": school_notice,
        "school_notice_lines": _notice_lines(school_notice),
        "period_order": ["1", "2", "3", "4", "5a", "5b / Lunch", "6", "7"],
        "day_timetable_fields": DAY_TIMETABLE_FIELDS,
        "unsubscribe_url": "https://ashfordschool.co.uk",
    }


def generate_email_html(user_email):
    """Generate personalized email HTML for a specific user email."""

    db = get_db()
    c = db.cursor()
    c.execute("SELECT id, email, name, pin, send_emails, timetable_a, timetable_b, day_timetable, created_at FROM users WHERE email=?", (user_email,))
    user = _row_to_dict(c.fetchone())
    c.execute("SELECT id, holiday_mode, holiday_weeks, ab_week, menu_week, menu_week_1, menu_week_2, menu_week_3, school_notice FROM settings WHERE id=1")
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
        c.execute("SELECT id, email, name, pin, send_emails, timetable_a, timetable_b, day_timetable, created_at FROM users WHERE send_emails = 1")
        users = c.fetchall()
        c.execute("SELECT id, holiday_mode, holiday_weeks, ab_week, menu_week, menu_week_1, menu_week_2, menu_week_3, school_notice FROM settings WHERE id=1")
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
