import json
import html

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
    return {key: row[key] for key in row.keys()}


def _fetch_user(user_id):
    db = get_db()
    c = db.cursor()
    c.execute(
        """
        SELECT id, email, name, pin, send_emails, timetable_a, timetable_b, day_timetable, created_at
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
    if not raw_notice:
        return Markup("")

    if bleach is None or markdown_lib is None:
        escaped_notice = html.escape(str(raw_notice))
        paragraphs = [
            f"<p>{line}</p>"
            for line in escaped_notice.splitlines()
            if line.strip()
        ]
        return Markup("".join(paragraphs) or f"<p>{escaped_notice}</p>")

    rendered = markdown_lib.markdown(
        str(raw_notice),
        extensions=["extra", "nl2br", "sane_lists", "fenced_code"],
    )
    cleaned = bleach.clean(
        rendered,
        tags=[
            "p",
            "br",
            "strong",
            "em",
            "ul",
            "ol",
            "li",
            "blockquote",
            "pre",
            "code",
            "h1",
            "h2",
            "h3",
            "h4",
            "h5",
            "h6",
            "a",
            "hr",
        ],
        attributes={"a": ["href", "title", "rel", "target"]},
        protocols=["http", "https", "mailto"],
        strip=True,
    )
    return Markup(cleaned)


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
        "school_notice": school_notice,
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
        return redirect(url_for("dashboard"))
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
            c.execute("SELECT id FROM users WHERE email=?", (email,))
            
            if c.fetchone():
                flash("Email already registered", "warning")
                db.close()
                return redirect(url_for("signup"))
            
            # Hash PIN if provided
            pin_hash = generate_password_hash(pin) if pin else None
            
            # Create user
            c.execute("""
                INSERT INTO users (email, pin, send_emails)
                VALUES (?, ?, 1)
            """, (email, pin_hash))
            
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
            c.execute("SELECT id, pin FROM users WHERE email=?", (email,))
            user = c.fetchone()
            db.close()
            
            if not user:
                flash("Email not found. Please sign up.", "warning")
                return redirect(url_for("signup"))
            
            user_id = user[0]
            pin_hash = user[1]
            
            # If user has PIN, redirect to PIN verification
            if pin_hash:
                session["temp_user_id"] = user_id
                session["temp_user_email"] = email
                return redirect(url_for("pin_verify"))
            
            # No PIN - log in directly
            session["user_id"] = user_id
            session["user_email"] = email
            session["login_time"] = datetime.now().isoformat()
            
            # Check if this email is an admin email
            is_admin_email = email.lower() in [admin_email.lower() for admin_email in ADMIN_EMAILS]
            
            if is_admin_email:
                # Admin user without PIN - show dashboard choice
                session["is_admin_email"] = True
                flash("Logged in successfully", "success")
                return redirect(url_for("dashboard_choice"))
            else:
                # Normal user - go straight to dashboard
                session["is_admin"] = False
                flash("Logged in successfully", "success")
                return redirect(url_for("dashboard"))
            
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
            c.execute("SELECT pin FROM users WHERE id=?", (temp_user_id,))
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
            session["user_email"] = temp_user_email
            session["login_time"] = datetime.now().isoformat()
            
            # Check if this email is an admin email
            is_admin_email = temp_user_email.lower() in [email.lower() for email in ADMIN_EMAILS]
            
            if is_admin_email:
                # Admin user - show dashboard choice
                session["is_admin_email"] = True
                session.pop("temp_user_id", None)
                session.pop("temp_user_email", None)
                flash("Logged in successfully", "success")
                return redirect(url_for("dashboard_choice"))
            else:
                # Normal user - go straight to dashboard
                session["is_admin"] = False
                session.pop("temp_user_id", None)
                session.pop("temp_user_email", None)
                flash("Logged in successfully", "success")
                return redirect(url_for("dashboard"))
            
        except Exception as e:
            print(f"[✗] PIN verification error: {e}")
            flash("Error verifying PIN", "danger")
            return redirect(url_for("pin_verify"))
    
    return render_template("pin.html", email=temp_user_email)


@app.route("/dashboard/choice")
def dashboard_choice():
    """Dashboard choice page for admin users."""
    if "user_id" not in session or not session.get("is_admin_email"):
        flash("Invalid request", "danger")
        return redirect(url_for("login"))
    
    return render_template("dashboard_choice.html", email=session.get("user_email"))


@app.route("/dashboard/choice/admin", methods=["POST"])
def dashboard_choice_admin():
    """Redirect to admin dashboard."""
    if "user_id" not in session or not session.get("is_admin_email"):
        flash("Invalid request", "danger")
        return redirect(url_for("login"))
    
    session["is_admin"] = True
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
    flash("Switched to User Dashboard", "success")
    return redirect(url_for("dashboard"))


@app.route("/logout")
def logout():
    """Logout user."""
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
            holiday_mode=settings["holiday_mode"],
            holiday_weeks=settings["holiday_weeks"],
            ab_week=settings["ab_week"],
            menu_week=settings["menu_week"],
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

        c.execute("SELECT id FROM users WHERE email=? AND id != ?", (email, session["user_id"]))
        if c.fetchone():
            db.close()
            flash("That email is already in use", "warning")
            return redirect(url_for("dashboard"))

        if new_pin:
            pin_hash = generate_password_hash(new_pin)
            c.execute(
                """
                UPDATE users
                SET email=?, name=?, pin=?
                WHERE id=?
                """,
                (email, name, pin_hash, session["user_id"]),
            )
        else:
            c.execute(
                """
                UPDATE users
                SET email=?, name=?
                WHERE id=?
                """,
                (email, name, session["user_id"]),
            )

        db.commit()
        db.close()

        session["user_email"] = email
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
        
        # Convert to list of dicts for easier template use
        users_list = []
        if users:
            for u in users:
                users_list.append({
                    'id': u[0],
                    'email': u[1],
                   'name': u[2],
                   'send_emails': u[3],
                   'created_at': u[4]
                })
        
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
        )
        
    except Exception as e:
        print(f"[✗] Admin dashboard error: {e}")
        flash("Error loading admin panel", "danger")
        return redirect(url_for("login"))


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
        
        c.execute("SELECT id FROM users WHERE email=?", (email,))
        if c.fetchone():
            flash("Email already exists", "warning")
            db.close()
            return redirect(url_for("admin_dashboard"))
        
        c.execute("""
            INSERT INTO users (email, name, pin, send_emails, timetable_a, timetable_b)
            VALUES (?, ?, ?, 1, ?, ?)
        """, (
            email,
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
            timetable_a = json.dumps(_timetable_form_data("timetable_a", request.form))
            timetable_b = json.dumps(_timetable_form_data("timetable_b", request.form))
            day_timetable = json.dumps(_serialize_day_timetable(request.form, "day_timetable"))

            db = get_db()
            c = db.cursor()

            c.execute("SELECT id FROM users WHERE email=? AND id != ?", (email, user_id))
            if c.fetchone():
                db.close()
                flash("That email is already in use", "warning")
                return redirect(url_for("admin_user_profile", user_id=user_id))

            if pin:
                c.execute(
                    """
                    UPDATE users
                    SET email=?, name=?, pin=?, send_emails=?, timetable_a=?, timetable_b=?, day_timetable=?
                    WHERE id=?
                    """,
                    (email, name, generate_password_hash(pin), send_emails, timetable_a, timetable_b, day_timetable, user_id),
                )
            else:
                c.execute(
                    """
                    UPDATE users
                    SET email=?, name=?, send_emails=?, timetable_a=?, timetable_b=?, day_timetable=?
                    WHERE id=?
                    """,
                    (email, name, send_emails, timetable_a, timetable_b, day_timetable, user_id),
                )

            db.commit()
            db.close()

            flash("Profile updated", "success")
            return redirect(url_for("admin_user_profile", user_id=user_id))

        settings = _settings_defaults(_fetch_settings())
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
            holiday_mode=settings["holiday_mode"],
            period_order=PERIOD_ORDER,
            day_timetable_fields=DAY_TIMETABLE_FIELDS,
            weekdays=WEEKDAYS,
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
        c.execute("SELECT id, email, name, pin, send_emails, timetable_a, timetable_b, day_timetable, created_at FROM users WHERE id=?", (user_id,))
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
