from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import pytz
from db import get_db
from emailer import send_email
from config import TIMEZONE, SCHEDULER_ENABLED


def generate_email_html(user_email):
    """Generate personalized email HTML for user."""
    html = f"""
    <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #1e3a8a;">📧 Daily School Update</h2>
                
                <p>Hello,</p>
                
                <p>Here is your daily update for today:</p>
                
                <div style="background: #f8f9fa; padding: 15px; border-left: 4px solid #1e3a8a; margin: 20px 0;">
                    <h3 style="margin-top: 0;">📅 Today's Schedule</h3>
                    <p>Check the portal for your updated timetable and events.</p>
                </div>
                
                <div style="background: #f8f9fa; padding: 15px; border-left: 4px solid #1e3a8a; margin: 20px 0;">
                    <h3 style="margin-top: 0;">🍽️ Lunch Menu</h3>
                    <p>Available in the canteen.</p>
                </div>
                
                <p style="color: #666; margin-top: 30px; font-size: 12px;">
                    Sent: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
                </p>
            </div>
        </body>
    </html>
    """
    return html


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
        c.execute("SELECT id, email FROM users WHERE send_emails = 1")
        users = c.fetchall()
        db.close()
        
        if not users:
            print("[ℹ] No users to send emails to")
            return
        
        # Send email to each user
        success_count = 0
        for user in users:
            user_id, email = user if isinstance(user, tuple) else (user['id'], user['email'])
            html = generate_email_html(email)
            
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
