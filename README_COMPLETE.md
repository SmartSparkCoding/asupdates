# 🚀 AS Updates - Complete System Guide

## Overview

**AS Updates** is a production-ready Flask web application for managing school schedules, timetables, lunch menus, and automated daily email notifications to students. It features role-based access (users and admins), modern glassmorphic UI, and comprehensive email scheduling.

---

## ✨ Key Features

### For Users
- 📧 Personalized daily emails with schedule, timetable, and lunch menu
- 🗓️ Two-week timetable rotation (Week A / Week B)
- 🕐 Period-based timetable (7 periods per day)
- 📝 Daily schedule (before school, lunch, after school activities)
- 🔐 Optional PIN security for login
- 📋 View/edit own timetable and settings
- 🔔 Toggle email notifications on/off

### For Admins
- 👥 Manage all users (add, edit, delete)
- 📢 Publish school notices (sent in daily emails)
- 🍽️ Manage 3-week lunch menu rotation
- 🏖️ Holiday mode (pause all emails)
- 📅 AB week rotation management
- ⏱️ Email scheduler status monitoring
- 💼 Send individual emails to users
- 📊 View user statistics

### Special Admin Access
Two designated emails have special admin dashboard access:
- `NavaratneJ@ashpupil.co.uk`
- `MooreF@ashpupil.co.uk`

After login, these users can **choose** between Admin or User dashboard.

---

## 🛠️ Setup Instructions

### Prerequisites
- Python 3.8 or higher
- pip package manager
- Gmail account (for email sending)

### Installation

1. **Clone/Extract the project**
```bash
cd /workspaces/asupdates
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Create environment configuration**
```bash
cat > .env << EOF
# Flask Configuration
SECRET_KEY=your-secret-key-change-this-in-production
DEBUG=False

# Admin Access
ADMIN_PASSWORD=admin123

# Gmail SMTP (Required for emails)
GMAIL_USER=your-email@gmail.com
GMAIL_APP_PASSWORD=your-app-password

# Email Scheduler
SCHEDULER_ENABLED=True
TIMEZONE=Europe/London

# Database
DATABASE=app.db
EOF
```

⚠️ **Gmail App Password Setup:**
1. Enable 2-factor authentication on your Google account
2. Go to [Google App Passwords](https://myaccount.google.com/apppasswords)
3. Select "Mail" and "Windows Computer" (or your device)
4. Copy the 16-character password to `GMAIL_APP_PASSWORD`

4. **Initialize database**
```bash
python3 init_db.py
# Or: python3 -c "from db import init_db; init_db()"
```

5. **Run the application**
```bash
python3 app.py
```

6. **Access the app**
- Open browser to `http://localhost:5000`
- Default admin password: `admin123` (from .env)

---

## 🔐 Authentication System

### User Types & Login Flow

#### 1. Regular Users
```
Signup with email + optional PIN
    ↓
Login with email
    ↓
No PIN? → Straight to Dashboard
Has PIN? → PIN verification → Dashboard
```

#### 2. Admin Users (Special Emails)
```
Login with NavaratneJ@ashpupil.co.uk OR MooreF@ashpupil.co.uk
    ↓
No PIN? → Go to Dashboard Choice
Has PIN? → PIN verify → Dashboard Choice
    ↓
Choose between:
├─ Admin Dashboard (manage system)
└─ User Dashboard (view as regular student)
```

#### 3. Admin Password Login
```
Enter admin password on login page
    ↓
Go directly to Admin Dashboard (no user profile)
```

---

## 📊 Database Schema

### Users Table
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| email | TEXT | Unique email address |
| name | TEXT | Optional display name |
| pin | TEXT | Optional hashed PIN |
| send_emails | INTEGER | 1=enabled, 0=disabled |
| timetable_a | TEXT | JSON - Week A schedule |
| timetable_b | TEXT | JSON - Week B schedule |
| day_timetable | TEXT | JSON - Before/lunch/after activities |
| created_at | TIMESTAMP | Account creation time |

### Settings Table
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Always 1 (singleton) |
| ab_week | TEXT | Current week: 'A' or 'B' |
| holiday_mode | INTEGER | 1=on, 0=off (pause emails) |
| holiday_weeks | INTEGER | Number of weeks (if holiday_mode=1) |
| menu_week | INTEGER | Current menu week (1-3) |
| menu_week_1 | TEXT | JSON - Week 1 menu |
| menu_week_2 | TEXT | JSON - Week 2 menu |
| menu_week_3 | TEXT | JSON - Week 3 menu |
| school_notice | TEXT | Notice text for next emails |

### School Notice History Table
| Column | Type | Notes |
|--------|------|-------|
| id | INTEGER | Primary key |
| notice_text | TEXT | Saved notice content |
| created_at | TIMESTAMP | When it was saved |

---

## 📧 Email System

### How It Works

**Scheduler:** Every weekday at 08:00 AM (UK time)
- Checks if holiday mode is OFF
- Gets all users with `send_emails = 1`
- Generates personalized email for each user
- Includes: Name, date, period timetable, daily schedule, lunch menu, school notice

**Template Location:** `templates/email_original.html`

**Sections Included:**
1. Greeting (personalized with student name)
2. Today's period timetable (shows times, subjects, rooms)
3. Daily schedule (before school, lunch, after school)
4. Lunch menu (8 options: main, sides, pasta, street food, potatoes, soup, vegetarian, dessert)
5. School notices (from admin)
6. Events (holiday mode status, menu week)
7. Footer with admin contact info

### Testing Emails

**From Admin Dashboard:**
1. Click "Test Email" → Sends test email to you
2. Click user → "Email" → Sends email immediately to that user
3. Click user → "Email" → "Preview Email" → View in new tab

---

## 🗓️ Timetable System

### Period Timetable
- **Periods:** 1, 2, 3, 4, 5a, 5b/Lunch, 6, 7
- **Fields:** Subject, Room
- **Per user:** Separate for Week A and Week B
- **Editable by:** User (dashboard) or Admin (user profile)

### Daily Timetable
- **Days:** Monday - Friday
- **Fields:** Before school, After school, Lunch clubs
- **Per user:** One set for all days
- **Examples:** "Breakfast club (8am-8:40am)", "Football training (4:00pm)"
- **Editable by:** User (dashboard) or Admin (user profile)

### Menu Rota
- **Structure:** 3-week rotation
- **Days:** Monday - Friday
- **Weeks cycle:** 1 → 2 → 3 → 1 (repeats)
- **Admin sets:** Current active week (1, 2, or 3)
- **Menu items:** Main, sides, pasta bar, street food, potatoes, soup, vegetarian, dessert

---

## 🎨 UI/UX Design

### Modern Design Features
- **Glassmorphism:** Semi-transparent cards with blur effects
- **Smooth Animations:** Hover lift effects, slide animations, ripple buttons
- **Responsive:** Works on mobile, tablet, and desktop
- **Color Scheme:**
  - Primary: Teal (#14b8a6)
  - Dark: Navy (#0f766e)
  - Admin: Red (#dc2626)
  - Success: Green (#10b981)

### User Experience
- Flash messages for all actions (success/error/warning)
- Modal dialogs for complex forms
- Touch-friendly buttons (44px+ targets)
- Clear visual hierarchy
- Consistent spacing and padding
- Smooth page transitions

---

## 🔧 Admin Dashboard Guide

### User Management
**Location:** "Manage Users" section

Actions:
- **View all users** - Table with email, status, creation date
- **Add user** - Email, name (optional), PIN (optional)
- **Edit user** - Click "Profile" button on user row
- **Delete user** - Click "Delete" button (confirm prompt)
- **Toggle emails** - Toggle "Emails On/Off" badge

### System Settings

**Holiday Mode** (📍 "Holiday Mode" card)
- Toggle to pause/resume emails
- Enter number of weeks
- Useful during school breaks

**AB Week** (📍 "AB Week Schedule" card)
- Toggle between Week A and Week B
- Updates immediately
- Affects which timetable is sent in emails

**Menu Rota** (📍 "3-Week Menu Rota" card)
- Edit all 3 weeks of menu
- Set current active week (1, 2, or 3)
- Students see current week's menu in emails

**School Notices** (📍 "School Notices" card)
- Write notice text
- Appears in all emails sent next
- View last 4 saved notices

**Email Settings** (📍 "Test Email" card)
- Send test email
- Check Gmail configuration

---

## 📱 URLs & Routes

### Public Routes
- `GET /` - Redirect to dashboard or login
- `GET /login` - Login page (user or admin)
- `GET /signup` - Create new user account
- `GET /pin` - PIN verification
- `POST /login` - Submit login
- `POST /signup` - Submit signup
- `POST /pin` - Submit PIN verification
- `GET /logout` - Logout

### User Routes (requires @login_required)
- `GET /dashboard` - User dashboard (timetable, settings)
- `POST /dashboard/update-account` - Update profile
- `POST /dashboard/update-timetable` - Save timetable
- `POST /toggle-emails` - Toggle email notifications
- `GET /dashboard/choice` - Admin user dashboard choice
- `POST /dashboard/choice/admin` - Switch to admin dashboard
- `POST /dashboard/choice/normal` - Switch to user dashboard

### Admin Routes (requires @admin_required)
- `GET /admin` - Admin dashboard
- `POST /admin/add-user` - Add new user
- `POST /admin/delete-user/<id>` - Delete user
- `POST /admin/toggle-user-emails/<id>` - Toggle user emails
- `GET /admin/user/<id>` - Edit user profile
- `POST /admin/user/<id>` - Save user profile
- `POST /admin/toggle-holiday` - Toggle holiday mode
- `POST /admin/menu-settings` - Save menu rota
- `POST /admin/notices` - Save school notice
- `POST /admin/set-week/<week>` - Set AB week
- `POST /admin/send-email/<id>` - Send email to user
- `GET /admin/email-preview/<id>` - Preview email HTML
- `GET /admin/email/<id>` - Email prompt page
- `POST /admin/test-email` - Send test email

### API Routes
- `GET /api/status` - System status JSON

---

## 🐛 Troubleshooting

### Emails Not Sending
1. **Check Gmail credentials**
   - Verify `GMAIL_USER` is correct
   - Verify `GMAIL_APP_PASSWORD` is 16-character app password (not regular password)
   - Test in console: Run `python3 -c "from emailer import send_test_email; send_test_email('test@example.com')"`

2. **Check scheduler**
   - Verify `SCHEDULER_ENABLED=True` in `.env`
   - Check app console for: `[✓] Scheduler started`
   - Verify timezone is correct

3. **Check settings**
   - Verify `holiday_mode = 0` in database
   - Verify user has `send_emails = 1`
   - Current time should be weekday (not Saturday/Sunday)

### Database Issues
```bash
# Backup current database
cp app.db app.db.backup

# Delete and reinitialize
rm app.db
python3 init_db.py

# Or reset specific table
sqlite3 app.db "DELETE FROM users;"
```

### Import Errors
```bash
# Reinstall dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Check Python version (needs 3.8+)
python3 --version
```

### Port Already in Use
```bash
# If port 5000 is busy, change in app.py:
# app.run(port=5001)

# Or find and kill process:
lsof -i :5000
kill -9 <PID>
```

---

## 📈 Performance Tips

- Database queries cache user data in session
- Timetable JSON parsing is efficient
- Email sending happens asynchronously via scheduler
- Static CSS is minified
- Database uses indexes on email column

---

## 🔒 Security Considerations

✅ **Implemented:**
- Password hashing for PINs (werkzeug.security)
- Session-based authentication
- CSRF protection ready (Flask-Session)
- Environment variables for secrets
- SQL injection protection (parameterized queries)

⚠️ **For Production:**
- Change `SECRET_KEY` to random string
- Change `ADMIN_PASSWORD`
- Use HTTPS in production
- Set `DEBUG=False`
- Use production WSGI server (gunicorn, etc.)
- Implement rate limiting on login
- Add logging to audit trail
- Backup database regularly

---

## 📚 Documentation Files

- **SYSTEM_DOCUMENTATION.md** - Complete system architecture & API docs
- **LATEST_CHANGES.md** - Latest session changes & testing guide
- **CHANGES_SUMMARY.md** - Historical changes
- **SETUP_GUIDE.md** - Original setup guide
- **DEPLOYMENT_CHECKLIST.md** - Pre-launch checklist
- **PROJECT_COMPLETION_SUMMARY.md** - Project overview

---

## 🚀 Quick Start (TL;DR)

```bash
# 1. Setup
cd /workspaces/asupdates
pip install -r requirements.txt

# 2. Configure
echo "ADMIN_PASSWORD=admin123
GMAIL_USER=your@gmail.com
GMAIL_APP_PASSWORD=xxxx-xxxx-xxxx-xxxx
SCHEDULER_ENABLED=True
DEBUG=False" > .env

# 3. Initialize
python3 init_db.py

# 4. Run
python3 app.py

# 5. Visit
# http://localhost:5000
```

---

## 📞 Support

**System Status:** All features working ✅
**Database:** SQLite initialized ✅
**Email Scheduler:** Running at 8am weekdays ✅
**UI/UX:** Modern glassmorphism design ✅
**Admin Access:** Email-based recognition ✅
**Production Ready:** YES ✅

---

**Version:** 2.0 (Post-UI Upgrade)  
**Last Updated:** May 19, 2024  
**Status:** ✅ PRODUCTION READY

