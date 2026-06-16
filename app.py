import json
import html
import uuid

from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from markupsafe import Markup
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os
from dotenv import load_dotenv

try:
    import bleach
except ImportError:  # pragma: no cover - graceful fallback for unprepared environments
    bleach = None

try:
    import markdown as markdown_lib
except ImportError:  # pragma: no cover - graceful fallback for unprepared environments
    markdown_lib = None

from config import SECRET_KEY, ADMIN_PASSWORD, DEBUG, DATABASE
from db import get_db, init_db, verify_schema
from emailer import send_test_email, send_email
from scheduler import start_scheduler, generate_email_html
from email_security import decrypt_email, encrypt_email, email_lookup_value, normalize_email
from homework import fetch_homework_items, homework_email_summary, split_homework
from markdown_email import render_markdown_html, embed_markdown_images
from email_templates import (
    WEEKDAYS,
    PERIOD_ORDER,
    SCHEDULE_FIELDS,
    DAY_TIMETABLE_FIELDS,
    PERIOD_TIMES,
    default_timetable,
    default_week_schedule,
    default_day_timetable,
    parse_timetable,
    parse_week_schedule,
    parse_week_menu,
    render_email_html,
    schedule_day_row,
    schedule_rows,
    serialize_timetable,
    serialize_week_schedule,
    serialize_week_menu,
    timetable_day_rows,
    timetable_rows,
    render_mailing_list_email_html,
)

# Load environment variables
load_dotenv()

# Admin emails that have access to admin dashboard
ADMIN_EMAILS = [
    "NavaratneJ@ashpupil.co.uk",
    "MooreF@ashpupil.co.uk",
]

# Initialize Flask app
app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['SESSION_TYPE'] = 'filesystem'
APP_START_TIME = datetime.now()

# Initialize database
if not verify_schema():
    init_db()

# Start background scheduler
scheduler = start_scheduler()


# ============================================================================
# DECORATORS
# ============================================================================

def login_required(f):
    """Require user to be logged in."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    """Require user to be logged in as admin."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "is_admin" not in session or not session["is_admin"]:
            flash("Admin access required", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def _row_to_dict(row):
    if not row:
        return {}
    data = {key: row[key] for key in row.keys()}
    if "email" in data:
        data["email"] = decrypt_email(data["email"])
    return data


def _user_lookup(email):
    return email_lookup_value(email)


def _fetch_user(user_id):
    db = get_db()
    c = db.cursor()
    c.execute(
        """
        SELECT id, email, name, pin, send_emails, timetable_a, timetable_b, homework_in_email, day_timetable, created_at
        FROM users
        WHERE id=?
        """,
        (user_id,)
    )
    user = c.fetchone()
    db.close()
    return _row_to_dict(user)


def _fetch_settings():
    db = get_db()
    c = db.cursor()
    c.execute(
        """
        SELECT id, holiday_mode, holiday_weeks, ab_week, menu_week, menu_week_1, menu_week_2, menu_week_3, school_notice
        FROM settings
        WHERE id=1
        """
    )
    settings = c.fetchone()
    db.close()
    return _row_to_dict(settings)


def _session_key():
    if "session_key" not in session:
        session["session_key"] = uuid.uuid4().hex
    return session["session_key"]


def _track_active_session(user_id, is_admin=False):
    if not user_id:
        return

    db = get_db()
    c = db.cursor()
    session_key = _session_key()
    c.execute(
        """
        INSERT INTO active_sessions (session_key, user_id, is_admin, last_seen)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(session_key) DO UPDATE SET
            user_id=excluded.user_id,
            is_admin=excluded.is_admin,
            last_seen=CURRENT_TIMESTAMP
        """,
        (session_key, user_id, 1 if is_admin else 0),
    )
    db.commit()
    db.close()


def _clear_active_session():
    session_key = session.get("session_key")
    if not session_key:
        return
    db = get_db()
    c = db.cursor()
    c.execute("DELETE FROM active_sessions WHERE session_key=?", (session_key,))
    db.commit()
    db.close()


def _app_uptime():
    delta = datetime.now() - APP_START_TIME
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)
    if days:
        return f"{days}d {hours}h {minutes}m"
    if hours:
        return f"{hours}h {minutes}m"
    return f"{minutes}m {seconds}s"


def _active_logged_in_users(minutes=30):
    db = get_db()
    c = db.cursor()
    c.execute(
        """
        SELECT u.id, u.email, u.name, s.last_seen, s.is_admin
        FROM active_sessions s
        JOIN users u ON u.id = s.user_id
        WHERE datetime(s.last_seen) >= datetime('now', ?)
        ORDER BY datetime(s.last_seen) DESC
        """,
        (f"-{minutes} minutes",),
    )
    rows = [_row_to_dict(row) for row in c.fetchall()]
    db.close()
    return rows


@app.before_request
def _refresh_active_session():
    if "user_id" in session:
        _track_active_session(session["user_id"], bool(session.get("is_admin")))


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


def _render_markdown_notice(raw_notice):
    return Markup(render_markdown_html(raw_notice))


def _mailing_list_placeholder_map(user):
    user = user or {}
    display_name = (user.get("name") or "").strip() or (user.get("email") or "").strip() or "Recipient"
    email = (user.get("email") or "").strip()
    return {
        "{(user_name)}": display_name,
        "{(user_email)}": email,
    }


def _replace_mailing_list_placeholders(text, user):
    text = str(text or "")
    for placeholder, value in _mailing_list_placeholder_map(user).items():
        text = text.replace(placeholder, value)
    return text


def _fetch_mailing_lists():
    db = get_db()
    c = db.cursor()
    c.execute(
        """
        SELECT ml.*, COUNT(m.user_id) AS member_count
        FROM mailing_lists ml
        LEFT JOIN mailing_list_members m ON m.list_id = ml.id
        GROUP BY ml.id
        ORDER BY datetime(ml.updated_at) DESC, datetime(ml.created_at) DESC, ml.id DESC
        """
    )
    lists = [_row_to_dict(row) for row in c.fetchall()]
    db.close()
    return lists


def _fetch_mailing_list(list_id):
    db = get_db()
    c = db.cursor()
    c.execute("SELECT * FROM mailing_lists WHERE id=?", (list_id,))
    mailing_list = _row_to_dict(c.fetchone())
    db.close()
    return mailing_list


def _fetch_mailing_list_members(list_id):
    db = get_db()
    c = db.cursor()
    c.execute(
        """
        SELECT u.id, u.email, u.name, u.send_emails
        FROM users u
        INNER JOIN mailing_list_members mlm ON mlm.user_id = u.id
        WHERE mlm.list_id=?
        ORDER BY COALESCE(NULLIF(u.name, ''), u.email) COLLATE NOCASE
        """,
        (list_id,),
    )
    members = [_row_to_dict(row) for row in c.fetchall()]
    db.close()
    return members


def _fetch_users_for_select():
    db = get_db()
    c = db.cursor()
    c.execute("SELECT id, email, name, send_emails FROM users ORDER BY COALESCE(NULLIF(name, ''), email) COLLATE NOCASE")
    users = [_row_to_dict(row) for row in c.fetchall()]
    db.close()
    return users


def _render_mailing_list_email(mailing_list, recipient, preview=False):
    mailing_list = mailing_list or {}
    recipient = recipient or {}
    mode = (mailing_list.get("email_mode") or "premade").strip().lower()
    title = _replace_mailing_list_placeholders(mailing_list.get("title", ""), recipient)
    subject = _replace_mailing_list_placeholders(mailing_list.get("subject", ""), recipient)
    footer_text = _replace_mailing_list_placeholders(mailing_list.get("footer_html", ""), recipient)
    footer_html = render_markdown_html(footer_text)

    if mode == "manual":
        body_html = _replace_mailing_list_placeholders(mailing_list.get("manual_html", ""), recipient)
        body_html = embed_markdown_images(body_html)
        signature_html = ""
    else:
        body_markdown = _replace_mailing_list_placeholders(mailing_list.get("body_text", ""), recipient)
        signature_markdown = _replace_mailing_list_placeholders(mailing_list.get("signature_text", ""), recipient)
        body_html = render_markdown_html(body_markdown)
        signature_html = render_markdown_html(signature_markdown)

    context = {
        "list_name": mailing_list.get("name", "Mailing List"),
        "description": mailing_list.get("description", ""),
        "email_mode": mode,
        "title": title or mailing_list.get("name", "Mailing List"),
        "subject": subject,
        "recipient_name": recipient.get("name") or recipient.get("email") or "Recipient",
        "recipient_email": recipient.get("email") or "",
        "body_html": Markup(body_html),
        "signature_html": Markup(signature_html),
        "footer_html": Markup(footer_html),
        "preview_mode": preview,
    }
    return render_mailing_list_email_html(context)


def _parse_menu_data(menu_text):
    """Parse menu text into structured dictionary with food types."""
    current_day = datetime.now().strftime("%A")
    weekly_menu = parse_week_menu(menu_text)
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


def _parse_period_start(period_time):
    if not period_time:
        return None
    start_text = str(period_time).split("-")[0].strip()
    try:
        return datetime.strptime(start_text, "%H:%M").time()
    except ValueError:
        return None


def _next_lesson_context(schedule_source, current_day, holiday_mode=0):
    if holiday_mode == 1:
        return {
            "next_lesson": None,
            "next_lesson_label": "After holiday",
            "next_lesson_hint": "School is paused for the holiday period.",
        }

    now = datetime.now()
    today_rows = timetable_day_rows(schedule_source, current_day) if current_day in WEEKDAYS else []
    current_start_time = now.time()

    for row in today_rows:
        if not row.get("subject") and not row.get("room"):
            continue
        start_time = _parse_period_start(row.get("time"))
        if start_time and start_time >= current_start_time:
            return {
                "next_lesson": row,
                "next_lesson_label": current_day,
                "next_lesson_hint": f"Today at {row.get('time')}",
            }

    current_index = WEEKDAYS.index(current_day) if current_day in WEEKDAYS else -1
    for offset in range(1, 8):
        day_name = WEEKDAYS[(current_index + offset) % len(WEEKDAYS)]
        rows = timetable_day_rows(schedule_source, day_name)
        next_row = next((row for row in rows if row.get("subject") or row.get("room")), None)
        if next_row:
            return {
                "next_lesson": next_row,
                "next_lesson_label": day_name,
                "next_lesson_hint": "Next school day",
            }

    return {
        "next_lesson": None,
        "next_lesson_label": "No lessons found",
        "next_lesson_hint": "Check your timetable in settings.",
    }


def _get_period_schedule(timetable):
    """Convert timetable to period-based schedule with times."""
    schedule = {}
    for period in PERIOD_ORDER:
        period_data = timetable.get(period, {})
        subject = (period_data or {}).get("subject", "").strip()
        room = (period_data or {}).get("room", "").strip()
        time = PERIOD_TIMES.get(period, "")
        
        schedule[period] = {
            "time": time,
            "subject": subject,
            "room": room,
        }
    return schedule


def _build_user_email_context(user, settings, external_url_base=None):
    current_week = settings.get("ab_week", "A")
    timetable_raw = user.get("timetable_a", "") if current_week == "A" else user.get("timetable_b", "")
    timetable = parse_timetable(timetable_raw)
    day_timetable = _parse_day_timetable(user.get("day_timetable", ""))
    current_day = datetime.now().strftime("%A")
    current_day_schedule = {row["period"]: row for row in timetable_day_rows(timetable, current_day)} if current_day in WEEKDAYS else {}
    current_day_timetable = day_timetable.get(current_day, {}) if current_day in WEEKDAYS else {}
    homework_items = []
    homework_summary = {}
    homework_enabled = user.get("homework_in_email", 1) == 1
    if user.get("id") and homework_enabled:
        db = get_db()
        homework_items = fetch_homework_items(db, user.get("id"))
        homework_summary = homework_email_summary(homework_items)
        db.close()
    
    menu_week = max(1, min(3, int(settings.get("menu_week", 1) or 1)))
    menu_text = settings.get(f"menu_week_{menu_week}", "")
    menu_data = _parse_menu_data(menu_text)
    
    school_notice = settings.get("school_notice", "")
    school_notice_html = Markup(render_markdown_html(school_notice))
    display_name = user.get("name") or user.get("email", "").split("@")[0].replace(".", " ").title() or "Student"

    return {
        "name": display_name,
        "current_date": datetime.now().strftime("%A, %d %B %Y"),
        "sent_datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "day_name": current_day,
        "day_schedule": current_day_schedule,
        "current_day_schedule": current_day_schedule,
        "current_day_timetable": current_day_timetable,
        "current_week_schedule": timetable_day_rows(timetable, current_day) if current_day in WEEKDAYS else [],
        "lunch": menu_data,
        "menu_week": menu_week,
        "events": [
            f"Holiday mode: {'ON' if settings.get('holiday_mode') == 1 else 'OFF'}",
            f"Current rota week: {menu_week}",
        ],
        "updates": [
            f"Email updates are {'enabled' if user.get('send_emails', 1) == 1 else 'disabled'} for this account.",
            f"Use the dashboard to update your profile and timetable.",
        ],
        "homework_items": homework_items,
        "homework_summary": homework_summary,
        "homework_enabled": homework_enabled,
        "school_notice": school_notice,
        "school_notice_html": school_notice_html,
        "school_notice_lines": _notice_lines(school_notice),
        "period_order": PERIOD_ORDER,
        "day_timetable_fields": DAY_TIMETABLE_FIELDS,
        "unsubscribe_url": external_url_base or url_for("dashboard", _external=True),
    }


def _render_user_email(user, settings):
    return render_email_html(_build_user_email_context(user, settings))


def _timetable_form_data(prefix, form_data):
    return serialize_timetable(form_data, prefix)


def _parse_day_timetable(raw_value):
    """Parse day timetable (before/after school, lunch clubs) from JSON."""
    if not raw_value:
        return default_day_timetable()
    
    if isinstance(raw_value, dict):
        result = default_day_timetable()
        for day in WEEKDAYS:
            if day in raw_value and isinstance(raw_value[day], dict):
                for field in DAY_TIMETABLE_FIELDS:
                    result[day][field] = str(raw_value[day].get(field, "")).strip()
        return result
    
    try:
        parsed = json.loads(raw_value)
        return _parse_day_timetable(parsed)
    except (TypeError, ValueError):
        return default_day_timetable()


def _serialize_day_timetable(form_data, prefix):
    """Serialize day timetable from form data into JSON."""
    timetable = default_day_timetable()
    for day in WEEKDAYS:
        slug = day.lower()
        for field in DAY_TIMETABLE_FIELDS:
            timetable[day][field] = form_data.get(f"{prefix}_{slug}_{field}", "").strip()
    return timetable


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", 
                          error_code=404, 
                          error_message="Page not found"), 404


@app.errorhandler(500)
def server_error(error):
    return render_template("error.html", 
                          error_code=500, 
                          error_message="Server error"), 500


# ============================================================================
# HOME / LANDING
# ============================================================================

@app.route("/")
def home():
    """Landing page - redirect based on session."""
    if "is_admin_email" in session and session["is_admin_email"]:
        return redirect(url_for("dashboard_choice"))
    elif "is_admin" in session and session["is_admin"]:
        return redirect(url_for("admin_dashboard"))
    elif "user_id" in session:
        if session.get("dashboard_mode") == "new":
            return redirect(url_for("dashboard_new"))
        if session.get("dashboard_mode") == "old":
            return redirect(url_for("dashboard"))
        return redirect(url_for("dashboard_choice"))
    else:
        return redirect(url_for("login"))


# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route("/signup", methods=["GET", "POST"])
def signup():
    """User signup page."""
    
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        pin = request.form.get("pin", "").strip()
        
        # Validate input
        if not email:
            flash("Email is required", "danger")
            return redirect(url_for("signup"))
        
        if "@" not in email:
            flash("Please enter a valid email", "danger")
            return redirect(url_for("signup"))
        
        # Check if user already exists
        try:
            db = get_db()
            c = db.cursor()
            c.execute("SELECT id FROM users WHERE email_lookup=?", (_user_lookup(email),))
            
            if c.fetchone():
                flash("Email already registered", "warning")
                db.close()
                return redirect(url_for("signup"))
            
            # Hash PIN if provided
            pin_hash = generate_password_hash(pin) if pin else None
            
            # Create user
            c.execute("""
                INSERT INTO users (email, email_lookup, pin, send_emails)
                VALUES (?, ?, ?, 1)
            """, (encrypt_email(email), _user_lookup(email), pin_hash))
            
            db.commit()
            db.close()
            
            flash("Account created! Please log in.", "success")
            return redirect(url_for("login"))
            
        except Exception as e:
            print(f"[✗] Signup error: {e}")
            flash("Error creating account. Please try again.", "danger")
            return redirect(url_for("signup"))
    
    return render_template("signup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """User login - email entry."""
    
    if request.method == "POST":
        # Check if this is admin login
        password = request.form.get("password", "").strip()
        email = request.form.get("email", "").strip().lower()
        
        # Admin login path
        if password:
            if password == ADMIN_PASSWORD:
                session["is_admin"] = True
                session["admin_login_time"] = datetime.now().isoformat()
                flash("Admin logged in", "success")
                return redirect(url_for("admin_dashboard"))
            else:
                flash("Invalid admin password", "danger")
                return redirect(url_for("login"))
        
        # User login path
        if not email:
            flash("Email is required", "danger")
            return redirect(url_for("login"))
        
        try:
            db = get_db()
            c = db.cursor()
            c.execute("SELECT id, pin, email FROM users WHERE email_lookup=?", (_user_lookup(email),))
            user = c.fetchone()
            db.close()
            
            if not user:
                flash("Email not found. Please sign up.", "warning")
                return redirect(url_for("signup"))
            
            user_id = user[0]
            pin_hash = user[1]
            resolved_email = decrypt_email(user[2]) or email
            
            # If user has PIN, redirect to PIN verification
            if pin_hash:
                session["temp_user_id"] = user_id
                session["temp_user_email"] = resolved_email
                return redirect(url_for("pin_verify"))
            
            # No PIN - log in directly
            session["user_id"] = user_id
            session["user_email"] = resolved_email
            session["login_time"] = datetime.now().isoformat()
            _session_key()
            
            # Check if this email is an admin email
            is_admin_email = resolved_email.lower() in [admin_email.lower() for admin_email in ADMIN_EMAILS]
            
            if is_admin_email:
                # Admin user without PIN - show dashboard choice
                session["is_admin_email"] = True
                _track_active_session(user_id, True)
                flash("Logged in successfully", "success")
                return redirect(url_for("dashboard_choice"))
            else:
                # Normal user - go straight to dashboard
                session["is_admin"] = False
                _track_active_session(user_id, False)
                flash("Logged in successfully", "success")
                return redirect(url_for("dashboard_choice"))
            
        except Exception as e:
            print(f"[✗] Login error: {e}")
            flash("Error logging in. Please try again.", "danger")
            return redirect(url_for("login"))
    
    return render_template("login.html")


@app.route("/pin", methods=["GET", "POST"])
def pin_verify():
    """PIN verification page."""
    
    temp_user_id = session.get("temp_user_id")
    temp_user_email = session.get("temp_user_email")
    
    if not temp_user_id:
        flash("Invalid request", "danger")
        return redirect(url_for("login"))
    
    if request.method == "POST":
        pin = request.form.get("pin", "").strip()
        
        if not pin:
            flash("Please enter your PIN", "danger")
            return redirect(url_for("pin_verify"))
        
        try:
            db = get_db()
            c = db.cursor()
            c.execute("SELECT pin, email FROM users WHERE id=?", (temp_user_id,))
            user = c.fetchone()
            db.close()
            
            if not user or not user[0]:
                flash("PIN not set for this account", "danger")
                return redirect(url_for("login"))
            
            # Verify PIN
            if not check_password_hash(user[0], pin):
                flash("Incorrect PIN", "danger")
                return redirect(url_for("pin_verify"))
            
            # PIN correct - log in
            session["user_id"] = temp_user_id
            session["user_email"] = decrypt_email(user[1]) or temp_user_email
            session["login_time"] = datetime.now().isoformat()
            _session_key()
            
            # Check if this email is an admin email
            is_admin_email = session["user_email"].lower() in [email.lower() for email in ADMIN_EMAILS]
            
            if is_admin_email:
                # Admin user - show dashboard choice
                session["is_admin_email"] = True
                session.pop("temp_user_id", None)
                session.pop("temp_user_email", None)
                _track_active_session(temp_user_id, True)
                flash("Logged in successfully", "success")
                return redirect(url_for("dashboard_choice"))
            else:
                # Normal user - go straight to dashboard
                session["is_admin"] = False
                session.pop("temp_user_id", None)
                session.pop("temp_user_email", None)
                _track_active_session(temp_user_id, False)
                flash("Logged in successfully", "success")
                return redirect(url_for("dashboard_choice"))
            
        except Exception as e:
            print(f"[✗] PIN verification error: {e}")
            flash("Error verifying PIN", "danger")
            return redirect(url_for("pin_verify"))
    
    return render_template("pin.html", email=temp_user_email)


@app.route("/dashboard/choice")
def dashboard_choice():
    """Dashboard choice page for all signed-in users."""
    if "user_id" not in session:
        flash("Invalid request", "danger")
        return redirect(url_for("login"))
    
    return render_template(
        "dashboard_choice.html",
        email=session.get("user_email"),
        can_access_admin=bool(session.get("is_admin_email")),
    )


@app.route("/dashboard/choice/admin", methods=["POST"])
def dashboard_choice_admin():
    """Redirect to admin dashboard."""
    if "user_id" not in session or not session.get("is_admin_email"):
        flash("Invalid request", "danger")
        return redirect(url_for("login"))
    
    session["is_admin"] = True
    session["dashboard_mode"] = "admin"
    session.pop("is_admin_email", None)
    flash("Switched to Admin Dashboard", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/dashboard/choice/normal", methods=["POST"])
def dashboard_choice_normal():
    """Redirect to normal user dashboard."""
    if "user_id" not in session:
        flash("Invalid request", "danger")
        return redirect(url_for("login"))
    
    session["is_admin"] = False
    session.pop("is_admin_email", None)
    session["dashboard_mode"] = "old"
    flash("Switched to User Dashboard", "success")
    return redirect(url_for("dashboard"))


@app.route("/dashboard/choice/old", methods=["POST"])
def dashboard_choice_old():
    return dashboard_choice_normal()


@app.route("/dashboard/choice/new", methods=["POST"])
@login_required
def dashboard_choice_new():
    """Redirect a normal user to the new dashboard."""

    session["is_admin"] = False
    session.pop("is_admin_email", None)
    session["dashboard_mode"] = "new"
    flash("Switched to New Dashboard", "success")
    return redirect(url_for("dashboard_new"))


@app.route("/logout")
def logout():
    """Logout user."""
    _clear_active_session()
    session.clear()
    flash("Logged out successfully", "info")
    return redirect(url_for("login"))


# ============================================================================
# USER DASHBOARD
# ============================================================================

@app.route("/dashboard")
@login_required
def dashboard():
    """User dashboard."""
    
    try:
        user = _fetch_user(session["user_id"])
        settings = _settings_defaults(_fetch_settings())
        schedule_a = parse_timetable(user.get("timetable_a", ""))
        schedule_b = parse_timetable(user.get("timetable_b", ""))
        day_timetable = _parse_day_timetable(user.get("day_timetable", ""))
        current_week = settings["ab_week"]
        current_day = datetime.now().strftime("%A")
        current_schedule_source = schedule_a if current_week == "A" else schedule_b
        current_day_periods = {row["period"]: row for row in timetable_day_rows(current_schedule_source, current_day)} if current_day in WEEKDAYS else {}
        
        return render_template(
            "dashboard.html",
            user=user,
            email=user.get("email", session.get("user_email")),
            name=user.get("name", ""),
            send_emails=user.get("send_emails", 1),
            homework_in_email=user.get("homework_in_email", 1),
            email_send_time=user.get("email_send_time", "08:00"),
            holiday_mode=settings["holiday_mode"],
            holiday_weeks=settings["holiday_weeks"],
            ab_week=settings["ab_week"],
            menu_week_1=settings["menu_week_1"],
            menu_week_2=settings["menu_week_2"],
            menu_week_3=settings["menu_week_3"],
            timetable_a=schedule_a,
            timetable_b=schedule_b,
            day_timetable=day_timetable,
            current_week=current_week,
            current_day=current_day,
            current_schedule=current_day_periods,
            current_week_schedule=timetable_day_rows(current_schedule_source, current_day) if current_day in WEEKDAYS else [],
            weekdays=WEEKDAYS,
            day_timetable_fields=DAY_TIMETABLE_FIELDS,
            schedule_fields=SCHEDULE_FIELDS,
            current_week_key=current_week,
            period_order=PERIOD_ORDER,
            period_times=PERIOD_TIMES,
        )
        
    except Exception as e:
        print(f"[✗] Dashboard error: {e}")
        flash("Error loading dashboard", "danger")
        return redirect(url_for("login"))


@app.route("/dashboard/new")
@login_required
def dashboard_new():
    """New student dashboard."""

    try:
        user = _fetch_user(session["user_id"])
        settings = _settings_defaults(_fetch_settings())
        schedule_a = parse_timetable(user.get("timetable_a", ""))
        schedule_b = parse_timetable(user.get("timetable_b", ""))
        day_timetable = _parse_day_timetable(user.get("day_timetable", ""))
        current_week = settings["ab_week"]
        current_day = datetime.now().strftime("%A")
        current_schedule_source = schedule_a if current_week == "A" else schedule_b
        current_day_periods = {row["period"]: row for row in timetable_day_rows(current_schedule_source, current_day)} if current_day in WEEKDAYS else {}

        next_lesson_context = _next_lesson_context(current_schedule_source, current_day, settings["holiday_mode"])
        menu_week = max(1, min(3, int(settings.get("menu_week", 1) or 1)))
        lunch_data = _parse_menu_data(settings.get(f"menu_week_{menu_week}", ""))
        homework_db = get_db()
        homework_items = fetch_homework_items(homework_db, user.get("id"))
        homework_sections = split_homework(homework_items)
        homework_db.close()

        return render_template(
            "dashboard_new.html",
            user=user,
            email=user.get("email", session.get("user_email")),
            name=user.get("name", ""),
            send_emails=user.get("send_emails", 1),
            homework_in_email=user.get("homework_in_email", 1),
            email_send_time=user.get("email_send_time", "08:00"),
            holiday_mode=settings["holiday_mode"],
            holiday_weeks=settings["holiday_weeks"],
            ab_week=settings["ab_week"],
            menu_week_1=settings["menu_week_1"],
            menu_week_2=settings["menu_week_2"],
            menu_week_3=settings["menu_week_3"],
            timetable_a=schedule_a,
            timetable_b=schedule_b,
            day_timetable=day_timetable,
            current_week=current_week,
            current_day=current_day,
            current_schedule=current_day_periods,
            current_week_schedule=timetable_day_rows(current_schedule_source, current_day) if current_day in WEEKDAYS else [],
            next_lesson=next_lesson_context["next_lesson"],
            next_lesson_label=next_lesson_context["next_lesson_label"],
            next_lesson_hint=next_lesson_context["next_lesson_hint"],
            lunch=lunch_data,
            menu_week=menu_week,
            homework_items=homework_items,
            homework_sections=homework_sections,
            weekdays=WEEKDAYS,
            day_timetable_fields=DAY_TIMETABLE_FIELDS,
            schedule_fields=SCHEDULE_FIELDS,
            current_week_key=current_week,
            period_order=PERIOD_ORDER,
            period_times=PERIOD_TIMES,
        )

    except Exception as e:
        print(f"[✗] New dashboard error: {e}")
        flash("Error loading new dashboard", "danger")
        return redirect(url_for("dashboard"))


@app.route("/dashboard/settings")
@login_required
def dashboard_settings():
    """Dedicated student settings page for the new dashboard."""

    try:
        user = _fetch_user(session["user_id"])
        settings = _settings_defaults(_fetch_settings())
        homework_db = get_db()
        homework_items = fetch_homework_items(homework_db, user.get("id"))
        homework_sections = split_homework(homework_items)
        homework_db.close()

        return render_template(
            "dashboard_settings.html",
            user=user,
            email=user.get("email", session.get("user_email")),
            name=user.get("name", ""),
            homework_in_email=user.get("homework_in_email", 1),
            email_send_time=user.get("email_send_time", "08:00"),
            current_theme="system",
            homework_items=homework_items,
            homework_sections=homework_sections,
            holiday_mode=settings["holiday_mode"],
        )

    except Exception as e:
        print(f"[✗] Dashboard settings error: {e}")
        flash("Error loading settings", "danger")
        return redirect(url_for("dashboard_new"))


@app.route("/homework")
@login_required
def homework_dashboard():
    """Dedicated homework management page."""

    try:
        user = _fetch_user(session["user_id"])
        homework_db = get_db()
        homework_items = fetch_homework_items(homework_db, user.get("id"))
        homework_sections = split_homework(homework_items)
        homework_db.close()

        return render_template(
            "homework.html",
            user=user,
            homework_items=homework_items,
            homework_sections=homework_sections,
        )

    except Exception as e:
        print(f"[✗] Homework dashboard error: {e}")
        flash("Error loading homework area", "danger")
        return redirect(url_for("dashboard_new"))


@app.route("/homework/add", methods=["POST"])
@login_required
def homework_add():
    """Add a homework item for the current user."""

    subject = request.form.get("subject", "").strip()
    title = request.form.get("title", "").strip()
    details = request.form.get("details", "").strip()
    due_date = request.form.get("due_date", "").strip()
    due_time = request.form.get("due_time", "23:59").strip() or "23:59"

    if not subject or not title or not due_date:
        flash("Subject, title, and due date are required", "warning")
        return redirect(url_for("dashboard_new"))

    try:
        db = get_db()
        c = db.cursor()
        c.execute(
            """
            INSERT INTO homework_items (user_id, subject, title, details, due_date, due_time, completed)
            VALUES (?, ?, ?, ?, ?, ?, 0)
            """,
            (session["user_id"], subject, title, details, due_date, due_time),
        )
        db.commit()
        db.close()
        flash("Homework added", "success")
    except Exception as e:
        print(f"[✗] Homework add error: {e}")
        flash("Error adding homework", "danger")

    return redirect(url_for("dashboard_new"))


@app.route("/homework/toggle/<int:item_id>", methods=["POST"])
@login_required
def homework_toggle(item_id):
    """Toggle a homework item's completion state."""

    try:
        db = get_db()
        c = db.cursor()
        c.execute("SELECT completed FROM homework_items WHERE id=? AND user_id=?", (item_id, session["user_id"]))
        row = c.fetchone()
        if not row:
            db.close()
            flash("Homework item not found", "warning")
            return redirect(url_for("dashboard_new"))

        new_value = 0 if row[0] else 1
        c.execute("UPDATE homework_items SET completed=? WHERE id=? AND user_id=?", (new_value, item_id, session["user_id"]))
        db.commit()
        db.close()
        flash("Homework updated", "success")
    except Exception as e:
        print(f"[✗] Homework toggle error: {e}")
        flash("Error updating homework", "danger")

    return redirect(url_for("dashboard_new"))


@app.route("/homework/delete/<int:item_id>", methods=["POST"])
@login_required
def homework_delete(item_id):
    """Delete a homework item."""

    try:
        db = get_db()
        c = db.cursor()
        c.execute("DELETE FROM homework_items WHERE id=? AND user_id=?", (item_id, session["user_id"]))
        db.commit()
        db.close()
        flash("Homework deleted", "success")
    except Exception as e:
        print(f"[✗] Homework delete error: {e}")
        flash("Error deleting homework", "danger")

    return redirect(url_for("dashboard_new"))


@app.route("/dashboard/update-account", methods=["POST"])
@login_required
def dashboard_update_account():
    """Update the logged in user's account details."""

    try:
        email = request.form.get("email", "").strip().lower()
        name = request.form.get("name", "").strip()
        new_pin = request.form.get("pin", "").strip()

        if not email:
            flash("Email is required", "danger")
            return redirect(url_for("dashboard"))

        db = get_db()
        c = db.cursor()

        c.execute("SELECT id FROM users WHERE email_lookup=? AND id != ?", (_user_lookup(email), session["user_id"]))
        if c.fetchone():
            db.close()
            flash("That email is already in use", "warning")
            return redirect(url_for("dashboard"))

        if new_pin:
            pin_hash = generate_password_hash(new_pin)
            c.execute(
                """
                UPDATE users
                SET email=?, email_lookup=?, name=?, pin=?
                WHERE id=?
                """,
                (encrypt_email(email), _user_lookup(email), name, pin_hash, session["user_id"]),
            )
        else:
            c.execute(
                """
                UPDATE users
                SET email=?, email_lookup=?, name=?
                WHERE id=?
                """,
                (encrypt_email(email), _user_lookup(email), name, session["user_id"]),
            )

        db.commit()
        db.close()

        session["user_email"] = normalize_email(email)
        flash("Account updated", "success")
    except Exception as e:
        print(f"[✗] Update account error: {e}")
        flash("Error updating account", "danger")

    return redirect(url_for("dashboard"))


@app.route("/dashboard/update-timetable", methods=["POST"])
@login_required
def dashboard_update_timetable():
    """Update the logged in user's weekday timetable and daily schedule."""

    try:
        timetable_a = json.dumps(serialize_timetable(request.form, "timetable_a"))
        timetable_b = json.dumps(serialize_timetable(request.form, "timetable_b"))
        day_timetable = json.dumps(_serialize_day_timetable(request.form, "day_timetable"))

        db = get_db()
        c = db.cursor()
        c.execute(
            """
            UPDATE users
            SET timetable_a=?, timetable_b=?, day_timetable=?
            WHERE id=?
            """,
            (timetable_a, timetable_b, day_timetable, session["user_id"]),
        )
        db.commit()
        db.close()

        flash("Timetable updated", "success")
    except Exception as e:
        print(f"[✗] Update timetable error: {e}")
        flash("Error updating timetable", "danger")

    return redirect(url_for("dashboard"))


@app.route("/toggle-emails", methods=["POST"])
@login_required
def toggle_emails():
    """Toggle email sending for user."""
    
    try:
        db = get_db()
        c = db.cursor()
        
        c.execute("SELECT send_emails FROM users WHERE id=?", (session["user_id"],))
        result = c.fetchone()
        current = result[0] if result else 1
        new_value = 1 - current
        
        c.execute("UPDATE users SET send_emails=? WHERE id=?", 
                 (new_value, session["user_id"]))
        db.commit()
        db.close()
        
        status = "enabled" if new_value else "disabled"
        flash(f"Emails {status}", "success")
        
    except Exception as e:
        print(f"[✗] Toggle emails error: {e}")
        flash("Error updating setting", "danger")
    
    return redirect(url_for("dashboard"))


@app.route("/dashboard/update-email-time", methods=["POST"])
@login_required
def dashboard_update_email_time():
    """Update user's preferred email send time."""
    
    try:
        email_send_time = request.form.get("email_send_time", "08:00")
        
        # Validate time format (HH:MM)
        if not email_send_time or len(email_send_time.split(":")) != 2:
            flash("Invalid time format", "danger")
            return redirect(url_for("dashboard"))
        
        db = get_db()
        c = db.cursor()
        c.execute(
            "UPDATE users SET email_send_time=? WHERE id=?",
            (email_send_time, session["user_id"])
        )
        db.commit()
        db.close()
        
        flash(f"Email time updated to {email_send_time}", "success")
        
    except Exception as e:
        print(f"[✗] Update email time error: {e}")
        flash("Error updating email time", "danger")
    
    return redirect(url_for("dashboard"))


@app.route("/dashboard/toggle-homework-email", methods=["POST"])
@login_required
def dashboard_toggle_homework_email():
    """Toggle whether homework is included in daily emails."""

    try:
        db = get_db()
        c = db.cursor()
        c.execute("SELECT homework_in_email FROM users WHERE id=?", (session["user_id"],))
        result = c.fetchone()
        current = result[0] if result else 1
        new_value = 1 - current

        c.execute("UPDATE users SET homework_in_email=? WHERE id=?", (new_value, session["user_id"]))
        db.commit()
        db.close()

        flash(f"Homework will now be {'included' if new_value else 'hidden'} in daily emails", "success")
    except Exception as e:
        print(f"[✗] Toggle homework email error: {e}")
        flash("Error updating homework setting", "danger")

    return redirect(url_for("dashboard"))


# ============================================================================
# ADMIN DASHBOARD
# ============================================================================

@app.route("/admin")
@admin_required
def admin_dashboard():
    """Admin dashboard."""
    
    try:
        db = get_db()
        c = db.cursor()
        
        # Get all users
        c.execute("""
            SELECT id, email, name, send_emails, created_at
            FROM users
            ORDER BY created_at DESC
        """)
        users = c.fetchall()

        c.execute(
            """
            SELECT user_id, id, subject, title, due_date, due_time, completed
            FROM homework_items
            ORDER BY due_date ASC, due_time ASC, created_at DESC
            """
        )
        homework_rows = c.fetchall()
        
        # Get settings
        c.execute("SELECT holiday_mode, holiday_weeks, ab_week, menu_week, menu_week_1, menu_week_2, menu_week_3, school_notice FROM settings WHERE id=1")
        settings = c.fetchone()
        c.execute("SELECT notice_text, created_at FROM school_notice_history ORDER BY created_at DESC LIMIT 4")
        notice_history = c.fetchall()
        
        db.close()
        
        holiday_mode = settings[0] if settings else 0
        holiday_weeks = settings[1] if settings else 0
        ab_week = settings[2] if settings else "A"
        menu_week = settings[3] if settings else 1
        menu_week_1 = settings[4] if settings else ""
        menu_week_2 = settings[5] if settings else ""
        menu_week_3 = settings[6] if settings else ""
        school_notice = settings[7] if settings else ""
        menu_week_1_data = parse_week_menu(menu_week_1)
        menu_week_2_data = parse_week_menu(menu_week_2)
        menu_week_3_data = parse_week_menu(menu_week_3)
        user_count = len(users) if users else 0
        notice_history_rendered = [
            {
                "created_at": item[1],
                "notice_html": _render_markdown_notice(item[0]),
            }
            for item in notice_history
        ]
        active_sessions = _active_logged_in_users()
        c.execute("SELECT COUNT(*) FROM mailing_lists")
        mailing_list_count_row = c.fetchone()
        mailing_list_count = mailing_list_count_row[0] if mailing_list_count_row else 0
        
        # Convert to list of dicts for easier template use
        homework_by_user = {}
        for homework in homework_rows or []:
            homework_item = _row_to_dict(homework)
            homework_by_user.setdefault(homework_item.get("user_id"), []).append(homework_item)

        users_list = []
        if users:
            for u in users:
                user_dict = _row_to_dict(u)
                user_homework = homework_by_user.get(user_dict.get("id"), [])
                user_homework_sections = split_homework(user_homework)
                user_dict["homework_count"] = len(user_homework)
                user_dict["pending_homework_count"] = user_homework_sections["pending_count"]
                user_dict["next_homework"] = user_homework_sections["next_homework"]
                users_list.append(user_dict)
        
        return render_template(
            "admin.html",
            users=users_list,
            user_count=user_count,
            holiday_mode=holiday_mode,
            holiday_weeks=holiday_weeks,
            ab_week=ab_week,
            menu_week=menu_week,
            menu_week_1=menu_week_1_data,
            menu_week_2=menu_week_2_data,
            menu_week_3=menu_week_3_data,
            school_notice=school_notice,
            school_notice_html=_render_markdown_notice(school_notice),
            notice_history=notice_history_rendered,
            weekdays=WEEKDAYS,
            menu_fields=["main", "sides", "pasta_bar", "street_food", "potatoes", "soup", "vegetarian", "dessert"],
            homework_items=homework_rows,
            app_uptime=_app_uptime(),
            active_sessions=active_sessions,
            active_session_count=len(active_sessions),
            mailing_list_count=mailing_list_count,
        )
        
    except Exception as e:
        print(f"[✗] Admin dashboard error: {e}")
        flash("Error loading admin panel", "danger")
        return redirect(url_for("login"))


@app.route("/admin/mailing-lists", methods=["GET"])
@admin_required
def admin_mailing_lists():
    """Manage mailing lists and compose list emails."""

    try:
        mailing_lists = _fetch_mailing_lists()
        users = _fetch_users_for_select()
        db = get_db()
        c = db.cursor()
        c.execute("SELECT list_id, user_id FROM mailing_list_members")
        membership_rows = c.fetchall()
        db.close()

        membership_map = {}
        for row in membership_rows:
            membership_map.setdefault(row[0], []).append(row[1])

        for mailing_list in mailing_lists:
            member_ids = membership_map.get(mailing_list.get("id"), [])
            mailing_list["member_ids"] = member_ids
            mailing_list["member_count"] = len(member_ids)

        return render_template(
            "admin_mailing_lists.html",
            mailing_lists=mailing_lists,
            users=users,
            list_modes=["premade", "manual"],
            preview_member_id=request.args.get("preview_member_id", type=int),
        )

    except Exception as e:
        print(f"[✗] Mailing lists page error: {e}")
        flash("Error loading mailing lists", "danger")
        return redirect(url_for("admin_dashboard"))


@app.route("/admin/mailing-lists/create", methods=["POST"])
@admin_required
def admin_mailing_lists_create():
    """Create a new mailing list."""

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()

    if not name:
        flash("Mailing list name is required", "warning")
        return redirect(url_for("admin_mailing_lists"))

    try:
        db = get_db()
        c = db.cursor()
        c.execute(
            """
            INSERT INTO mailing_lists (name, description, email_mode, title, subject, body_text, signature_text, manual_html, footer_html)
            VALUES (?, ?, 'premade', ?, ?, ?, ?, ?, ?)
            """,
            (
                name,
                description,
                name,
                f"{name} update",
                "",
                "",
                "",
                "",
            ),
        )
        db.commit()
        db.close()
        flash(f"Mailing list '{name}' created", "success")
    except Exception as e:
        print(f"[✗] Mailing list create error: {e}")
        flash("Error creating mailing list", "danger")

    return redirect(url_for("admin_mailing_lists"))


@app.route("/admin/mailing-lists/<int:list_id>", methods=["POST"])
@admin_required
def admin_mailing_lists_update(list_id):
    """Update a mailing list and replace its members."""

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()
    email_mode = request.form.get("email_mode", "premade").strip().lower()
    title = request.form.get("title", "").strip()
    subject = request.form.get("subject", "").strip()
    body_text = request.form.get("body_text", "").strip()
    signature_text = request.form.get("signature_text", "").strip()
    manual_html = request.form.get("manual_html", "").strip()
    footer_html = request.form.get("footer_html", "").strip()
    member_ids = [member_id for member_id in request.form.getlist("member_ids") if member_id]

    if not name:
        flash("Mailing list name is required", "warning")
        return redirect(url_for("admin_mailing_lists"))

    try:
        db = get_db()
        c = db.cursor()
        c.execute(
            """
            UPDATE mailing_lists
            SET name=?, description=?, email_mode=?, title=?, subject=?, body_text=?, signature_text=?, manual_html=?, footer_html=?, updated_at=CURRENT_TIMESTAMP
            WHERE id=?
            """,
            (name, description, email_mode, title, subject, body_text, signature_text, manual_html, footer_html, list_id),
        )
        c.execute("DELETE FROM mailing_list_members WHERE list_id=?", (list_id,))
        for member_id in member_ids:
            c.execute(
                "INSERT OR IGNORE INTO mailing_list_members (list_id, user_id) VALUES (?, ?)",
                (list_id, int(member_id)),
            )
        db.commit()
        db.close()
        flash(f"Mailing list '{name}' updated", "success")
    except Exception as e:
        print(f"[✗] Mailing list update error: {e}")
        flash("Error updating mailing list", "danger")

    return redirect(url_for("admin_mailing_lists"))


@app.route("/admin/mailing-lists/<int:list_id>/preview", methods=["GET"])
@admin_required
def admin_mailing_lists_preview(list_id):
    """Render a preview of a mailing list email."""

    mailing_list = _fetch_mailing_list(list_id)
    if not mailing_list:
        flash("Mailing list not found", "warning")
        return redirect(url_for("admin_mailing_lists"))

    preview_member_id = request.args.get("preview_member_id", type=int)
    recipient = None
    if preview_member_id:
        recipient = _fetch_user(preview_member_id)
    if not recipient:
        members = _fetch_mailing_list_members(list_id)
        if members:
            recipient = members[0]
    if not recipient:
        recipient = {"name": "Preview Recipient", "email": "preview@example.com"}

    return _render_mailing_list_email(mailing_list, recipient, preview=True)


@app.route("/admin/mailing-lists/<int:list_id>/send", methods=["POST"])
@admin_required
def admin_mailing_lists_send(list_id):
    """Send a mailing list message to all enabled members."""

    mailing_list = _fetch_mailing_list(list_id)
    if not mailing_list:
        flash("Mailing list not found", "warning")
        return redirect(url_for("admin_mailing_lists"))

    try:
        members = _fetch_mailing_list_members(list_id)
        if not members:
            flash("Mailing list has no members", "warning")
            return redirect(url_for("admin_mailing_lists"))

        db = get_db()
        c = db.cursor()
        sent_count = 0
        skipped_count = 0
        failed_count = 0

        for member in members:
            if int(member.get("send_emails", 1) or 1) != 1:
                skipped_count += 1
                continue

            subject = _replace_mailing_list_placeholders(
                mailing_list.get("subject", "") or mailing_list.get("title", "") or mailing_list.get("name", "Mailing List"),
                member,
            )
            html_content = _render_mailing_list_email(mailing_list, member, preview=False)
            if send_email(member.get("email", ""), subject, html_content):
                sent_count += 1
                c.execute(
                    "INSERT INTO mailing_list_sends (list_id, user_id, subject, email_mode) VALUES (?, ?, ?, ?)",
                    (list_id, member["id"], subject, mailing_list.get("email_mode", "premade")),
                )
            else:
                failed_count += 1

        db.commit()
        db.close()

        flash(
            f"Sent to {sent_count} member(s)" + (f", skipped {skipped_count}" if skipped_count else "") + (f", {failed_count} failed" if failed_count else ""),
            "success" if sent_count else "warning",
        )
    except Exception as e:
        print(f"[✗] Mailing list send error: {e}")
        flash("Error sending mailing list email", "danger")

    return redirect(url_for("admin_mailing_lists"))


@app.route("/admin/mailing-lists/<int:list_id>/delete", methods=["POST"])
@admin_required
def admin_mailing_lists_delete(list_id):
    """Delete a mailing list."""

    try:
        db = get_db()
        c = db.cursor()
        c.execute("SELECT name FROM mailing_lists WHERE id=?", (list_id,))
        mailing_list = c.fetchone()
        if not mailing_list:
            db.close()
            flash("Mailing list not found", "warning")
            return redirect(url_for("admin_mailing_lists"))

        c.execute("DELETE FROM mailing_lists WHERE id=?", (list_id,))
        db.commit()
        db.close()
        flash(f"Mailing list '{mailing_list[0]}' deleted", "success")
    except Exception as e:
        print(f"[✗] Mailing list delete error: {e}")
        flash("Error deleting mailing list", "danger")

    return redirect(url_for("admin_mailing_lists"))


@app.route("/admin/add-user", methods=["POST"])
@admin_required
def admin_add_user():
    """Add user from admin panel."""
    
    email = request.form.get("email", "").strip().lower()
    name = request.form.get("name", "").strip()
    pin = request.form.get("pin", "").strip()
    
    if not email:
        flash("Email is required", "danger")
        return redirect(url_for("admin_dashboard"))
    
    try:
        db = get_db()
        c = db.cursor()
        
        c.execute("SELECT id FROM users WHERE email_lookup=?", (_user_lookup(email),))
        if c.fetchone():
            flash("Email already exists", "warning")
            db.close()
            return redirect(url_for("admin_dashboard"))
        
        c.execute("""
            INSERT INTO users (email, email_lookup, name, pin, send_emails, timetable_a, timetable_b)
            VALUES (?, ?, ?, ?, 1, ?, ?)
        """, (
            encrypt_email(email),
            _user_lookup(email),
            name,
            generate_password_hash(pin) if pin else None,
            json.dumps(default_timetable()),
            json.dumps(default_timetable()),
        ))
        
        db.commit()
        db.close()
        
        flash(f"User {email} added", "success")
        
    except Exception as e:
        print(f"[✗] Add user error: {e}")
        flash("Error adding user", "danger")
    
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/delete-user/<int:user_id>", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    """Delete user from admin panel."""
    
    try:
        db = get_db()
        c = db.cursor()
        
        # Get user email for confirmation
        c.execute("SELECT email FROM users WHERE id=?", (user_id,))
        user = c.fetchone()
        
        if user:
            email = user[0]
            c.execute("DELETE FROM users WHERE id=?", (user_id,))
            db.commit()
            flash(f"User {email} deleted", "success")
        else:
            flash("User not found", "warning")
        
        db.close()
        
    except Exception as e:
        print(f"[✗] Delete user error: {e}")
        flash("Error deleting user", "danger")
    
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/toggle-user-emails/<int:user_id>", methods=["POST"])
@admin_required
def admin_toggle_user_emails(user_id):
    """Toggle email sending for a user from admin panel."""
    
    try:
        db = get_db()
        c = db.cursor()
        
        c.execute("SELECT send_emails, email FROM users WHERE id=?", (user_id,))
        result = c.fetchone()
        
        if result:
            current = result[0]
            email = result[1]
            new_value = 1 - current
            
            c.execute("UPDATE users SET send_emails=? WHERE id=?", (new_value, user_id))
            db.commit()
            
            status = "enabled" if new_value else "disabled"
            flash(f"Emails {status} for {email}", "success")
        else:
            flash("User not found", "warning")
        
        db.close()
        
    except Exception as e:
        print(f"[✗] Toggle user emails error: {e}")
        flash("Error updating user", "danger")
    
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/user/<int:user_id>", methods=["GET", "POST"])
@admin_required
def admin_user_profile(user_id):
    """View and edit a single user's complete profile."""

    try:
        user = _fetch_user(user_id)
        if not user:
            flash("User not found", "warning")
            return redirect(url_for("admin_dashboard"))

        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            name = request.form.get("name", "").strip()
            pin = request.form.get("pin", "").strip()
            send_emails = 1 if request.form.get("send_emails") == "on" else 0
            homework_in_email = 1 if request.form.get("homework_in_email") == "on" else 0
            timetable_a = json.dumps(_timetable_form_data("timetable_a", request.form))
            timetable_b = json.dumps(_timetable_form_data("timetable_b", request.form))
            day_timetable = json.dumps(_serialize_day_timetable(request.form, "day_timetable"))

            db = get_db()
            c = db.cursor()

            c.execute("SELECT id FROM users WHERE email_lookup=? AND id != ?", (_user_lookup(email), user_id))
            if c.fetchone():
                db.close()
                flash("That email is already in use", "warning")
                return redirect(url_for("admin_user_profile", user_id=user_id))

            if pin:
                c.execute(
                    """
                    UPDATE users
                    SET email=?, email_lookup=?, name=?, pin=?, send_emails=?, homework_in_email=?, timetable_a=?, timetable_b=?, day_timetable=?
                    WHERE id=?
                    """,
                    (encrypt_email(email), _user_lookup(email), name, generate_password_hash(pin), send_emails, homework_in_email, timetable_a, timetable_b, day_timetable, user_id),
                )
            else:
                c.execute(
                    """
                    UPDATE users
                    SET email=?, email_lookup=?, name=?, send_emails=?, homework_in_email=?, timetable_a=?, timetable_b=?, day_timetable=?
                    WHERE id=?
                    """,
                    (encrypt_email(email), _user_lookup(email), name, send_emails, homework_in_email, timetable_a, timetable_b, day_timetable, user_id),
                )

            db.commit()
            db.close()

            flash("Profile updated", "success")
            return redirect(url_for("admin_user_profile", user_id=user_id))

        settings = _settings_defaults(_fetch_settings())
        homework_db = get_db()
        homework_items = fetch_homework_items(homework_db, user_id)
        homework_sections = split_homework(homework_items)
        homework_db.close()
        user["timetable_a"] = parse_timetable(user.get("timetable_a", ""))
        user["timetable_b"] = parse_timetable(user.get("timetable_b", ""))
        user["day_timetable"] = _parse_day_timetable(user.get("day_timetable", ""))
        return render_template(
            "admin_profile.html",
            user=user,
            timetable_a=user["timetable_a"],
            timetable_b=user["timetable_b"],
            day_timetable=user["day_timetable"],
            send_emails=user.get("send_emails", 1),
            homework_in_email=user.get("homework_in_email", 1),
            holiday_mode=settings["holiday_mode"],
            period_order=PERIOD_ORDER,
            day_timetable_fields=DAY_TIMETABLE_FIELDS,
            weekdays=WEEKDAYS,
            homework_items=homework_items,
            homework_sections=homework_sections,
        )

    except Exception as e:
        print(f"[✗] Admin profile error: {e}")
        flash("Error loading user profile", "danger")
        return redirect(url_for("admin_dashboard"))


@app.route("/admin/send-email/<int:user_id>", methods=["POST"])
@admin_required
def admin_send_email(user_id):
    """Send an email immediately to a specific user (ignoring schedule/holiday mode)."""
    
    try:
        db = get_db()
        c = db.cursor()
        
        # Get user record
        c.execute("SELECT id, email, name, pin, send_emails, timetable_a, timetable_b, homework_in_email, day_timetable, created_at FROM users WHERE id=?", (user_id,))
        result = c.fetchone()
        
        if not result:
            flash("User not found", "warning")
            db.close()
            return redirect(url_for("admin_dashboard"))
        
        user = _row_to_dict(result)
        c.execute("SELECT id, holiday_mode, holiday_weeks, ab_week, menu_week, menu_week_1, menu_week_2, menu_week_3 FROM settings WHERE id=1")
        settings = _row_to_dict(c.fetchone())
        user_email = user.get("email")

        # Generate email HTML
        html_content = _render_user_email(user, _settings_defaults(settings))
        
        # Send the email immediately
        success = send_email(
            to_email=user_email,
            subject="School Update - Manual Send",
            html_content=html_content
        )
        
        db.close()
        
        if success:
            print(f"[✓] Email sent to {user_email} (manual)")
            flash(f"Email sent to {user_email}", "success")
        else:
            print(f"[✗] Email failed for {user_email} (manual)")
            flash(f"Failed to send email to {user_email}", "danger")
        
    except Exception as e:
        print(f"[✗] Send email error: {e}")
        flash(f"Error sending email: {str(e)}", "danger")
    
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/email/<int:user_id>", methods=["GET"])
@admin_required
def admin_email_prompt(user_id):
    """Show the on-site email prompt for preview or send."""

    user = _fetch_user(user_id)
    if not user:
        flash("User not found", "warning")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_email_prompt.html", user=user)


@app.route("/admin/email-preview/<int:user_id>")
@admin_required
def admin_email_preview(user_id):
    """Render the HTML email preview in a new tab."""

    user = _fetch_user(user_id)
    if not user:
        flash("User not found", "warning")
        return redirect(url_for("admin_dashboard"))

    settings = _settings_defaults(_fetch_settings())
    return _render_user_email(user, settings)


@app.route("/admin/toggle-holiday", methods=["POST"])
@admin_required
def admin_toggle_holiday():
    """Toggle holiday mode."""
    
    try:
        holiday_weeks = int(request.form.get("holiday_weeks", "0") or 0)
        db = get_db()
        c = db.cursor()
        
        c.execute("SELECT holiday_mode FROM settings WHERE id=1")
        result = c.fetchone()
        current = result[0] if result else 0
        new_value = 1 - current
        
        c.execute("UPDATE settings SET holiday_mode=?, holiday_weeks=? WHERE id=1", (new_value, holiday_weeks if new_value == 1 else 0))
        db.commit()
        db.close()
        
        if new_value:
            flash(f"Holiday mode ON for {holiday_weeks} week(s)", "success")
        else:
            flash("Holiday mode OFF", "success")
        
    except Exception as e:
        print(f"[✗] Toggle holiday error: {e}")
        flash("Error updating holiday mode", "danger")
    
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/menu-settings", methods=["POST"])
@admin_required
def admin_menu_settings():
    """Update the 3-week menu rota and active week."""

    try:
        menu_week = int(request.form.get("menu_week", "1") or 1)
        menu_week = max(1, min(3, menu_week))
        menu_week_1 = json.dumps(serialize_week_menu(request.form, "menu_week_1"))
        menu_week_2 = json.dumps(serialize_week_menu(request.form, "menu_week_2"))
        menu_week_3 = json.dumps(serialize_week_menu(request.form, "menu_week_3"))

        db = get_db()
        c = db.cursor()
        c.execute(
            """
            UPDATE settings
            SET menu_week=?, menu_week_1=?, menu_week_2=?, menu_week_3=?
            WHERE id=1
            """,
            (menu_week, menu_week_1, menu_week_2, menu_week_3),
        )
        db.commit()
        db.close()

        flash(f"Menu rota saved and week {menu_week} selected", "success")
    except Exception as e:
        print(f"[✗] Menu settings error: {e}")
        flash("Error updating menu rota", "danger")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/notices", methods=["POST"])
@admin_required
def admin_notices():
    """Update the school notice that is included in upcoming emails."""

    try:
        school_notice = request.form.get("school_notice", "").strip()

        db = get_db()
        c = db.cursor()
        c.execute("UPDATE settings SET school_notice=? WHERE id=1", (school_notice,))
        c.execute("INSERT INTO school_notice_history (notice_text) VALUES (?)", (school_notice,))
        db.commit()
        db.close()

        flash("School notice saved for the next email round", "success")
    except Exception as e:
        print(f"[✗] School notice error: {e}")
        flash("Error updating school notices", "danger")

    return redirect(url_for("admin_dashboard"))


@app.route("/admin/set-week/<week>", methods=["POST"])
@admin_required
def admin_set_week(week):
    """Set AB week."""
    
    if week not in ["A", "B"]:
        flash("Invalid week", "danger")
        return redirect(url_for("admin_dashboard"))
    
    try:
        db = get_db()
        c = db.cursor()
        c.execute("UPDATE settings SET ab_week=? WHERE id=1", (week,))
        db.commit()
        db.close()
        
        flash(f"Week set to {week}", "success")
        
    except Exception as e:
        print(f"[✗] Set week error: {e}")
        flash("Error updating week", "danger")
    
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/test-email", methods=["POST"])
@admin_required
def admin_test_email():
    """Send test email to admin."""
    
    try:
        admin_email = session.get("admin_email", "admin@example.com")
        
        if send_test_email(admin_email):
            flash("Test email sent (check console/email)", "success")
        else:
            flash("Failed to send test email (Gmail not configured?)", "warning")
            
    except Exception as e:
        print(f"[✗] Test email error: {e}")
        flash("Error sending test email", "danger")
    
    return redirect(url_for("admin_dashboard"))


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.route("/api/status")
def api_status():
    """API status endpoint for monitoring."""
    try:
        db = get_db()
        c = db.cursor()
        c.execute("SELECT COUNT(*) FROM users")
        user_count = c.fetchone()[0]
        db.close()
        
        return jsonify({
            "status": "ok",
            "timestamp": datetime.now().isoformat(),
            "users": user_count,
            "scheduler": "running" if scheduler else "stopped"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    print("[✓] Starting AS Updates Flask App...")
    print(f"[ℹ] Debug mode: {DEBUG}")
    print(f"[ℹ] Database: {DATABASE}")
    app.run(debug=DEBUG, host="0.0.0.0", port=5000)
