from flask import Flask, render_template, request, redirect, session, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import os
from dotenv import load_dotenv

from config import SECRET_KEY, ADMIN_PASSWORD, DEBUG, DATABASE
from db import get_db, init_db, verify_schema
from emailer import send_test_email
from scheduler import start_scheduler

# Load environment variables
load_dotenv()

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
    if "is_admin" in session and session["is_admin"]:
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
            session["is_admin"] = False
            session["login_time"] = datetime.now().isoformat()
            
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
            session["is_admin"] = False
            session["login_time"] = datetime.now().isoformat()
            
            # Clear temp session data
            session.pop("temp_user_id", None)
            session.pop("temp_user_email", None)
            
            flash("Logged in successfully", "success")
            return redirect(url_for("dashboard"))
            
        except Exception as e:
            print(f"[✗] PIN verification error: {e}")
            flash("Error verifying PIN", "danger")
            return redirect(url_for("pin_verify"))
    
    return render_template("pin.html", email=temp_user_email)


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
        db = get_db()
        c = db.cursor()
        
        # Get user info
        c.execute("""
            SELECT email, send_emails, created_at
            FROM users
            WHERE id=?
        """, (session["user_id"],))
        user = c.fetchone()
        
        # Get settings
        c.execute("SELECT holiday_mode, ab_week FROM settings WHERE id=1")
        settings = c.fetchone()
        
        db.close()
        
        holiday_mode = settings[0] if settings else 0
        ab_week = settings[1] if settings else "A"
        
        return render_template(
            "dashboard.html",
            email=user[0] if user else session.get("user_email"),
            send_emails=user[1] if user else 1,
            holiday_mode=holiday_mode,
            ab_week=ab_week
        )
        
    except Exception as e:
        print(f"[✗] Dashboard error: {e}")
        flash("Error loading dashboard", "danger")
        return redirect(url_for("login"))


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
            SELECT id, email, send_emails, created_at
            FROM users
            ORDER BY created_at DESC
        """)
        users = c.fetchall()
        
        # Get settings
        c.execute("SELECT holiday_mode, ab_week FROM settings WHERE id=1")
        settings = c.fetchone()
        
        db.close()
        
        holiday_mode = settings[0] if settings else 0
        ab_week = settings[1] if settings else "A"
        user_count = len(users) if users else 0
        
        # Convert to list of dicts for easier template use
        users_list = []
        if users:
            for u in users:
                users_list.append({
                    'id': u[0],
                    'email': u[1],
                    'send_emails': u[2],
                    'created_at': u[3]
                })
        
        return render_template(
            "admin.html",
            users=users_list,
            user_count=user_count,
            holiday_mode=holiday_mode,
            ab_week=ab_week
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
            INSERT INTO users (email, send_emails)
            VALUES (?, 1)
        """, (email,))
        
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


@app.route("/admin/toggle-holiday", methods=["POST"])
@admin_required
def admin_toggle_holiday():
    """Toggle holiday mode."""
    
    try:
        db = get_db()
        c = db.cursor()
        
        c.execute("SELECT holiday_mode FROM settings WHERE id=1")
        result = c.fetchone()
        current = result[0] if result else 0
        new_value = 1 - current
        
        c.execute("UPDATE settings SET holiday_mode=? WHERE id=1", (new_value,))
        db.commit()
        db.close()
        
        status = "ON" if new_value else "OFF"
        flash(f"Holiday mode {status}", "success")
        
    except Exception as e:
        print(f"[✗] Toggle holiday error: {e}")
        flash("Error updating holiday mode", "danger")
    
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
