# AS Updates - Flask School Schedule System

## Quick Start Guide

### 1. Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env

# Edit .env with your settings:
# - ADMIN_PASSWORD: Set a strong password for admin access
# - GMAIL_USER: Your Gmail address (optional for testing)
# - GMAIL_APP_PASSWORD: Gmail app-specific password (optional for testing)
```

### 2. Run Application

```bash
python3 app.py
```

The application will:
- ✓ Auto-create database (app.db)
- ✓ Initialize database schema
- ✓ Start the Flask server on http://localhost:5000
- ✓ Start the background scheduler (optional)

### 3. Access the App

- **User Portal**: http://localhost:5000
- **Admin Panel**: http://localhost:5000/admin
  - Default password: (set in .env ADMIN_PASSWORD)
- **API Status**: http://localhost:5000/api/status

---

## Features Implemented

### ✅ Authentication System
- Email-based signup/login
- Optional PIN verification
- Session-based security
- Admin authentication with password

### ✅ User Dashboard
- View account info
- Toggle email notifications
- View current week schedule
- See holiday mode status

### ✅ Admin Dashboard
- User management (add/delete/toggle emails)
- Holiday mode toggle
- AB week schedule management
- System status monitoring
- Test email functionality

### ✅ Database
- SQLite with proper schema
- Auto-initialization on first run
- Schema verification and repair
- Two tables: users, settings

### ✅ Email System
- Gmail SMTP integration
- HTML email templates
- Weekday-only scheduling (Mon-Fri)
- Dynamic content injection

### ✅ Scheduler
- Background job for daily emails
- Runs at 08:00 UK time
- Respects holiday mode
- Only sends to enabled users

### ✅ UI/UX
- Modern clean design (navy + white)
- Responsive mobile layout
- Professional cards and components
- Flash message alerts
- Error pages

---

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session secret | random-dev-key |
| `DEBUG` | Debug mode (True/False) | False |
| `ADMIN_PASSWORD` | Admin panel password | admin123 |
| `GMAIL_USER` | Gmail sender address | (empty) |
| `GMAIL_APP_PASSWORD` | Gmail app password | (empty) |
| `SCHEDULER_ENABLED` | Enable email scheduler | True |
| `TIMEZONE` | Scheduler timezone | Europe/London |

---

## Scheduler Details

### Email Sending Schedule
- **Days**: Monday - Friday (weekends skipped)
- **Time**: 08:00 AM UK Time
- **Holiday Mode**: Pauses all emails when enabled

### Configuration
- Edit admin dashboard to toggle holiday mode
- Change AB week schedule (Week A / Week B)

---

## User Flow

1. **New User**: Sign up → Create account with optional PIN
2. **Login**: Enter email → If PIN exists, verify PIN → Access dashboard
3. **Dashboard**: 
   - View account info
   - Enable/disable emails
   - See holiday mode status
4. **Emails**: 
   - Receive at 08:00 on weekdays
   - HTML formatted with timetable, events, lunch menu
   - Can disable from dashboard

---

## Admin Flow

1. **Login**: Click Admin tab → Enter password
2. **Dashboard**:
   - View all users
   - Delete users
   - Toggle email status per user
   - Add new users manually
   - Toggle holiday mode
   - Change week schedule
3. **Monitoring**:
   - Check system status
   - Send test emails
   - API status at /api/status

---

## Database Schema

### users table
```sql
- id: INTEGER PRIMARY KEY AUTOINCREMENT
- email: TEXT UNIQUE NOT NULL
- pin: TEXT (nullable)
- send_emails: INTEGER DEFAULT 1
- created_at: TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

### settings table
```sql
- id: INTEGER PRIMARY KEY
- holiday_mode: INTEGER DEFAULT 0
- ab_week: TEXT DEFAULT 'A'
```

---

## File Structure

```
/workspaces/asupdates/
├── app.py                 # Main Flask application
├── config.py             # Configuration settings
├── db.py                 # Database initialization & connection
├── emailer.py            # Gmail SMTP email sender
├── scheduler.py          # Background job scheduler
├── requirements.txt      # Python dependencies
├── app.db               # SQLite database (auto-created)
├── .env                 # Environment variables (create from .env.example)
├── static/
│   └── style.css        # Modern CSS styling
└── templates/
    ├── login.html       # Login page
    ├── signup.html      # Signup page
    ├── pin.html         # PIN verification
    ├── dashboard.html   # User dashboard
    ├── admin.html       # Admin panel
    ├── error.html       # Error pages
    └── email.html       # Email template
```

---

## Email Integration (Gmail)

### Setup Gmail SMTP

1. **Enable 2-factor authentication** on your Google account
2. **Generate App Password**:
   - Go to https://myaccount.google.com/apppasswords
   - Select "Mail" and "Windows Computer"
   - Copy the 16-character password
3. **Set Environment Variables**:
   ```bash
   GMAIL_USER=your.email@gmail.com
   GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
   ```
4. **Test**: Use admin panel "Send Test Email" button

### Email Template

Emails are sent with:
- Personal greeting
- Today's timetable
- Lunch menu
- Events/updates
- Professional formatting

---

## Troubleshooting

### Database Issues
- **"no such table: users"**: Delete app.db and restart (it will auto-initialize)
- **Schema mismatch**: The app verifies and repairs automatically

### Email Not Sending
1. Check GMAIL_USER and GMAIL_APP_PASSWORD in .env
2. Verify you're using app-specific password (not regular Gmail password)
3. Check admin panel "Test Email" for details
4. Check that 2-factor authentication is enabled on Gmail

### Scheduler Not Running
- Check `SCHEDULER_ENABLED=True` in .env
- Verify it's a weekday (Mon-Fri)
- Check if holiday mode is OFF
- Look for "Scheduler started" message on app startup

### Login Issues
- **PIN not working**: Make sure PIN was set during signup
- **Admin login fails**: Check ADMIN_PASSWORD in .env
- **Redirect loops**: Clear browser cookies and try again

---

## Security Notes

⚠️ **Production Deployment**:
- Change `SECRET_KEY` to a random string
- Set `DEBUG=False`
- Use a strong `ADMIN_PASSWORD`
- Use HTTPS in production
- Use proper database backups
- Don't commit .env file to git

---

## API Endpoints

### Public Endpoints
- `GET /` - Home (redirects based on session)
- `POST /signup` - Create account
- `POST /login` - Login page
- `GET /logout` - Logout

### Protected User Endpoints
- `GET /dashboard` - User dashboard
- `POST /toggle-emails` - Toggle email preference

### Protected Admin Endpoints
- `GET /admin` - Admin dashboard
- `POST /admin/add-user` - Add user
- `POST /admin/delete-user/<id>` - Delete user
- `POST /admin/toggle-user-emails/<id>` - Toggle user emails
- `POST /admin/toggle-holiday` - Toggle holiday mode
- `POST /admin/set-week/<A|B>` - Set AB week
- `POST /admin/test-email` - Send test email

### Public API
- `GET /api/status` - System status (JSON)

---

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review error messages in browser console
3. Check Flask server console output
4. Verify all environment variables are set

---

Last Updated: 2024-05-18
AS Updates v1.0
