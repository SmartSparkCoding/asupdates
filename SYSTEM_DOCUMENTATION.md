# AS Updates - System Documentation

## 📋 Overview

AS Updates is a comprehensive Flask-based web application for managing school schedules, timetables, menus, and automated email notifications. It serves both regular users and administrators with different levels of access and capabilities.

---

## 🏗️ Architecture

### Directory Structure
```
/workspaces/asupdates/
├── app.py                    # Main Flask application
├── config.py                 # Configuration settings
├── db.py                     # Database initialization & schema
├── emailer.py                # Email sending logic
├── scheduler.py              # Background email scheduler
├── email_templates.py        # Template parsing & utilities
├── requirements.txt          # Python dependencies
├── init_db.py               # Database initialization script
├── static/
│   └── style.css            # Global styling (glassmorphism design)
└── templates/
    ├── login.html           # Login page (dual tabs)
    ├── signup.html          # User signup
    ├── pin.html             # PIN verification
    ├── dashboard_choice.html # Admin dashboard selection page
    ├── dashboard.html       # User dashboard
    ├── admin.html           # Admin dashboard
    ├── admin_profile.html   # User profile editor (admin view)
    ├── admin_email_prompt.html  # Email sending interface
    ├── email_original.html  # Email template
    ├── error.html           # Error page
    └── ...
```

---

## 🔐 Authentication System

### User Types

#### 1. **Regular Users**
- Create account with email and optional PIN
- Access user dashboard to view schedule, timetable, menus
- Receive daily emails with personalized schedule
- Can edit own timetable and account settings

#### 2. **Admin Users (Email-Based)**
Two special admin emails have elevated access:
- `NavaratneJ@ashpupil.co.uk`
- `MooreF@ashpupil.co.uk`

After PIN verification, admin users see a **Dashboard Choice** page where they can select:
- **Admin Dashboard** → Manage all users, notices, schedules
- **User Dashboard** → View as regular user

#### 3. **Admin Password Login**
- Direct access via admin password (set in `ADMIN_PASSWORD` env var)
- Provides instant admin dashboard access (no user profile)

### Authentication Flow

**Regular User:**
```
Login (email) 
  → Has PIN? 
    → Yes: PIN Verify → Straight to Dashboard
    → No:  Direct to Dashboard
```

**Admin User (by email):**
```
Login (admin email)
  → Has PIN?
    → Yes: PIN Verify → Dashboard Choice
    → No:  Dashboard Choice
  → Select Admin/User Dashboard
```

**Admin (Password):**
```
Login (admin password) → Admin Dashboard
```

---

## 📊 Database Schema

### Tables

#### **users**
```sql
id              INTEGER PRIMARY KEY
email           TEXT UNIQUE NOT NULL
name            TEXT DEFAULT ''
pin             TEXT (hashed)
send_emails     INTEGER DEFAULT 1
timetable_a     TEXT (JSON) - Week A schedule
timetable_b     TEXT (JSON) - Week B schedule
day_timetable   TEXT (JSON) - Daily schedule (before/lunch/after)
created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

#### **settings**
```sql
id              INTEGER PRIMARY KEY (always 1)
holiday_mode    INTEGER DEFAULT 0 - Pause emails
holiday_weeks   INTEGER DEFAULT 0 - Number of holiday weeks
ab_week         TEXT DEFAULT 'A' - Current week rotation
menu_week       INTEGER DEFAULT 1 - Current menu week (1-3)
menu_week_1     TEXT (JSON) - Menu for week 1
menu_week_2     TEXT (JSON) - Menu for week 2
menu_week_3     TEXT (JSON) - Menu for week 3
school_notice   TEXT DEFAULT '' - Admin notice in emails
```

#### **school_notice_history**
```sql
id              INTEGER PRIMARY KEY
notice_text     TEXT NOT NULL
created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

---

## 🗓️ Timetable System

### Structure

#### **Period Timetable** (per user, Week A & B)
- **Periods:** 1, 2, 3, 4, 5a, 5b/Lunch, 6, 7
- **Fields per period:** subject, room
- **Stored as JSON:** `timetable_a` & `timetable_b` in users table
- **Example:**
```json
{
  "1": {"subject": "Maths", "room": "A101"},
  "2": {"subject": "English", "room": "B205"},
  ...
}
```

#### **Daily Timetable** (per user, per day)
- **Days:** Monday - Friday
- **Fields:** before_school, lunch_clubs, after_school
- **Stored as JSON:** `day_timetable` in users table
- **Example:**
```json
{
  "Monday": {
    "before_school": "Breakfast club in Hall",
    "lunch_clubs": "Science Club (D104)",
    "after_school": "Football training"
  },
  ...
}
```

#### **Weekly Schedule** (per user)
- **Days:** Monday - Friday
- **Fields:** before_school, break_time, lunch_time, after_school
- **Stored within:** `timetable_a` & `timetable_b` (JSON)
- **Note:** Currently not actively used in templates

#### **Menu Rota** (3-week rotation)
- **Weeks:** 1, 2, 3 (cycle repeats)
- **Days:** Monday - Friday
- **Fields:** main, sides, pasta_bar, street_food, potatoes, soup, vegetarian, dessert
- **Stored as JSON:** `menu_week_1`, `menu_week_2`, `menu_week_3` in settings
- **Admin sets:** which week is currently active (`menu_week`)

---

## 📧 Email System

### Configuration

**Environment Variables:**
```
GMAIL_USER              - Gmail sender address
GMAIL_APP_PASSWORD      - Gmail app password (NOT regular password)
SCHEDULER_ENABLED       - Enable/disable email scheduler (default: True)
TIMEZONE               - Timezone for scheduling (default: Europe/London)
```

### Scheduler

**When:** Every weekday (Mon-Fri) at 08:00 AM UK time

**Who:** All users with `send_emails = 1` (not in holiday mode)

**What:** Personalized email including:
- User's name
- Today's period timetable (based on current A/B week)
- Today's daily schedule (before/lunch/after)
- Lunch menu for current week
- School notices (from admin)
- Events & updates

### Email Template

**File:** `templates/email_original.html`

**Sections:**
1. **Greeting** - Personalized welcome
2. **Today's Timetable** - Period schedule with times, subjects, rooms
3. **Daily Activities** - Before/lunch/after school activities
4. **Lunch Menu** - All 8 menu options for the day
5. **School Notices** - Admin announcements
6. **Events** - System info (holiday mode, menu week)
7. **Footer** - Contact info for admins

### Manual Email Testing

**Admin Interface:**
- **Test Email button** → Sends test email to admin
- **Email user button** (from user list) → Send email immediately to specific user
- **Preview email** → HTML preview in new tab

---

## 🎨 UI/UX Design

### Modern Design Features

**Glassmorphism Effects:**
- Semi-transparent cards with backdrop blur
- Modern, clean aesthetic
- Enhanced depth and visual hierarchy

**Smooth Animations:**
- Card hover effects with lift
- Button ripple effects on click
- Slide-in animations for alerts
- Modal animations with easing

**Typography:**
- System font stack for optimal rendering
- Better letter-spacing for readability
- Consistent heading hierarchy
- Responsive font sizes

**Color Scheme:**
```
Primary:    Teal (#14b8a6)
Dark:       Navy (#0f766e)
Accent:     Red (#dc2626)
Neutral:    Gray scale (#6b7280, etc)
Success:    Green (#10b981)
Warning:    Amber (#f59e0b)
```

**Responsive Layout:**
- Mobile-first approach
- Flexible grids
- Touch-friendly buttons
- Optimized for all screen sizes

---

## 🔧 Admin Features

### User Management
- **Add users** - Name, email, optional PIN
- **Delete users** - Permanent removal
- **Edit profiles** - Full user data management
- **Toggle email** - Enable/disable notifications per user
- **View list** - All users with status and creation date

### System Settings

**Holiday Mode**
- Toggle to pause all emails
- Specify number of holiday weeks
- Prevents sending during breaks

**AB Week Rotation**
- Switch between Week A and Week B
- Affects which timetable is sent in emails
- Updates immediately

**3-Week Menu Rota**
- Edit all menu options for 3 weeks
- Set current active week (1-3)
- Manages lunch options (8 categories)

**School Notices**
- Add notice for next email round
- View last 4 saved notices
- Supports multi-line text

**Email System**
- View configuration status
- Test email functionality
- Monitor user send preferences
- See scheduler status

---

## 🚀 Setup & Deployment

### Requirements
- Python 3.8+
- SQLite3
- Gmail account with app password

### Installation Steps

1. **Clone/Extract Repository**
```bash
cd /workspaces/asupdates
```

2. **Create Virtual Environment (Optional but recommended)**
```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install Dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure Environment Variables**
Create `.env` file:
```
SECRET_KEY=your-secret-key-here
ADMIN_PASSWORD=your-admin-password
GMAIL_USER=your-email@gmail.com
GMAIL_APP_PASSWORD=your-app-password
SCHEDULER_ENABLED=True
TIMEZONE=Europe/London
DEBUG=False
```

5. **Initialize Database**
```bash
python3 init_db.py
# or
python3 -c "from db import init_db; init_db()"
```

6. **Run Application**
```bash
python3 app.py
```

Access at: `http://localhost:5000`

---

## 🔌 API Endpoints

### Status Check
- **GET** `/api/status` - Returns system status JSON
  ```json
  {
    "status": "ok",
    "timestamp": "2024-05-19T10:30:00",
    "users": 42,
    "scheduler": "running"
  }
  ```

---

## 🐛 Troubleshooting

### Emails Not Sending
1. Check Gmail credentials in `.env`
2. Enable "Less secure app access" or use app password
3. Check `SCHEDULER_ENABLED` setting
4. Verify holiday mode is OFF
5. Check user has `send_emails = 1`

### Database Issues
1. Delete `app.db` to recreate
2. Run `python3 init_db.py`
3. Verify file permissions

### Scheduler Not Starting
1. Check `SCHEDULER_ENABLED=True` in `.env`
2. Verify timezone is correct
3. Check logs for APScheduler errors

### Timetable Not Updating
1. Verify form data is being submitted correctly
2. Check database write permissions
3. Ensure JSON is being serialized properly

---

## 📝 Recent Updates

### Bug Fixes (Latest Session)
✅ Removed duplicate "School Notices" section in admin dashboard
✅ Implemented admin email user recognition (NavaratneJ@, MooreF@)
✅ Added dashboard choice page for admin users
✅ Upgraded UI with glassmorphism and modern design
✅ Improved CSS animations and responsive design
✅ Enhanced form styling with better feedback states

### Code Quality
- Clean separation of concerns
- Proper error handling
- Database transaction management
- Session-based authentication
- CSRF protection ready

---

## 🎯 Future Enhancements

- [ ] Dark mode toggle
- [ ] Email digest options (weekly, daily, etc.)
- [ ] Calendar view for timetable
- [ ] Mobile app integration
- [ ] Bulk user import (CSV)
- [ ] Custom email templates
- [ ] Two-factor authentication
- [ ] Activity logging
- [ ] Export functionality

---

## 📞 Support

For issues or questions:
- **Technical**: Check logs in console
- **Admin**: Contact NavaratneJ@ashpupil.co.uk or MooreF@ashpupil.co.uk

---

**Last Updated:** May 19, 2024
**Version:** 2.0 (Post-UI Upgrade)
