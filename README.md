# 📧 AS Updates - School Schedule & Email System

A modern, production-ready Flask application for sending personalized daily school updates and schedule information to students via email.

![Python](https://img.shields.io/badge/Python-3.7+-blue)
![Flask](https://img.shields.io/badge/Flask-3.0-green)
![SQLite](https://img.shields.io/badge/Database-SQLite-lightgrey)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

## ✨ Features

### 🔐 Authentication
- Email-based signup and login
- Optional PIN security for additional protection
- Session-based authentication
- Admin panel with password protection

### 📊 User Dashboard
- Edit name, email, and PIN from the account area
- Enter Week A and Week B timetables for periods 1 to 7
- Edit daily schedule with before school, after school, and lunch clubs for each weekday
- Toggle email notifications on/off
- Check current week schedule (A/B)
- View holiday mode status and current menu week
- Help and information section

### 🎛️ Admin Dashboard
- Manage all users (add, delete, profile, email preview, send emails)
- Edit each user's full profile, including PIN, periods timetable, and daily schedule
- Set holiday mode with a week-count prompt
- Manage AB week schedule
- Manage the 3-week lunch rota with a fullscreen menu editor and active menu week selector
- Edit school notices for the next email round and review the last 4 saved notices
- Send test emails
- Monitor system status
- API status endpoint

### 📧 Email System
- Gmail SMTP integration with TLS
- HTML-formatted emails
- Daily personalised updates
- Support for:
  - Student timetable
  - Events and announcements
  - Lunch menu information
  - Custom updates
- Preview the exact per-user HTML email before sending
- Automatic scheduling

### 📅 Smart Scheduler
- Sends emails weekdays only (Mon-Fri)
- 08:00 AM UK Time by default
- Holiday mode support (configurable)
- Background job execution
- No manual intervention needed

### 🎨 Modern UI
- Clean, professional design (Teal Green + White)
- Responsive mobile layout
- Intuitive navigation
- Flash message alerts
- Professional error pages

### 🛡️ Security
- Password hashing with werkzeug
- Session-based authentication
- @login_required and @admin_required decorators
- Input validation and sanitization
- HTTPS-ready configuration

---

## 🚀 Quick Start

### Prerequisites
- Python 3.7+
- pip (Python package manager)

### 1. Clone/Extract the Project
```bash
cd as-updates
```

### 2. Install Dependencies
**Linux/macOS:**
```bash
chmod +x start.sh
./start.sh
```

**Windows:**
```bash
start.bat
```

**Or manually:**
```bash
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
cp .env.example .env
# Edit .env with your settings:
# - ADMIN_PASSWORD: Your admin password
# - GMAIL_USER: (optional) your Gmail address
# - GMAIL_APP_PASSWORD: (optional) Gmail app password
```

### 4. Run the Application
```bash
python3 app.py
```

Access the app at: **http://localhost:5000**

---

## 📖 User Guide

### For Students
1. **Sign Up**: Create an account with your school email
2. **Set PIN** (Optional): Add extra security with a PIN
3. **Login**: Enter email, verify PIN if set
4. **Dashboard**: Manage email preferences and view settings

### For Administrators
1. **Login**: Click "Admin" tab, enter admin password
2. **Manage Users**: Add, delete, or toggle emails for users
3. **Set Holiday Mode**: Pause all emails during breaks
4. **Manage Schedule**: Switch between Week A and Week B
5. **Test System**: Send test emails to verify Gmail configuration

---

## 🔧 Configuration

### Environment Variables (.env file)

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | Flask session secret | Generated |
| `DEBUG` | Debug mode | False |
| `ADMIN_PASSWORD` | Admin login password | admin123 |
| `GMAIL_USER` | Gmail sender address | (empty) |
| `GMAIL_APP_PASSWORD` | Gmail app password | (empty) |
| `SCHEDULER_ENABLED` | Enable email scheduler | True |
| `TIMEZONE` | Scheduler timezone | Europe/London |

### Email Configuration (Gmail)

To enable email sending:

1. Enable 2-factor authentication on your Google account
2. Generate an App Password:
   - Go to https://myaccount.google.com/apppasswords
   - Select "Mail" and "Windows Computer"
   - Copy the 16-character password
3. Add to .env:
   ```
   GMAIL_USER=your.email@gmail.com
   GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
   ```

---

## 📂 Project Structure

```
as-updates/
├── app.py                      # Main Flask application
├── config.py                   # Configuration settings
├── db.py                       # Database management
├── emailer.py                  # Gmail email sender
├── scheduler.py                # Background job scheduler
├── requirements.txt            # Python dependencies
├── app.db                      # SQLite database (auto-created)
├── .env                        # Environment variables
├── .env.example               # Environment template
├── start.sh / start.bat       # Quick start scripts
│
├── static/
│   └── style.css             # Modern CSS styling
│
└── templates/
    ├── login.html            # Login/admin login page
    ├── signup.html           # User signup page
    ├── pin.html              # PIN verification
    ├── dashboard.html        # User dashboard
    ├── admin.html            # Admin dashboard
   ├── admin_profile.html    # Full user profile editor
   ├── admin_email_prompt.html # Preview/send prompt for email actions
    ├── error.html            # Error pages
    └── email.html            # Email template
```

---

## 🗄️ Database Schema

### users table
```sql
id           INTEGER PRIMARY KEY AUTOINCREMENT
email        TEXT UNIQUE NOT NULL
name         TEXT DEFAULT ''
pin          TEXT (nullable)
send_emails  INTEGER DEFAULT 1
timetable_a   TEXT DEFAULT ''
timetable_b   TEXT DEFAULT ''
created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
```

### settings table
```sql
id            INTEGER PRIMARY KEY
holiday_mode  INTEGER DEFAULT 0
holiday_weeks INTEGER DEFAULT 0
ab_week       TEXT DEFAULT 'A'
menu_week     INTEGER DEFAULT 1
menu_week_1   TEXT DEFAULT ''
menu_week_2   TEXT DEFAULT ''
menu_week_3   TEXT DEFAULT ''
```

---

## 🌐 API Endpoints

### Public Routes
- `GET /` - Home page
- `GET/POST /signup` - User registration
- `GET/POST /login` - User login
- `GET /logout` - User logout

### Protected Routes (Require Login)
- `GET /dashboard` - User dashboard
- `POST /dashboard/update-account` - Update account info and timetables
- `POST /toggle-emails` - Toggle email preferences
- `GET /pin` - PIN verification page

### Admin Routes (Require Admin Password)
- `GET /admin` - Admin dashboard
- `POST /admin/add-user` - Add new user
- `GET/POST /admin/user/<id>` - Full user profile editor
- `GET /admin/email/<id>` - On-site email preview/send prompt
- `GET /admin/email-preview/<id>` - Render the filled HTML email in a new tab
- `POST /admin/delete-user/<id>` - Delete user
- `POST /admin/toggle-holiday` - Toggle holiday mode
- `POST /admin/set-week/<A|B>` - Set AB week
- `POST /admin/menu-settings` - Save the 3-week lunch rota
- `POST /admin/test-email` - Send test email

### API Endpoints
- `GET /api/status` - System status (JSON)

---

## 🔄 Email Scheduling

### Default Schedule
- **Days**: Monday - Friday
- **Time**: 08:00 AM (UK Time)
- **Frequency**: Daily
- **Holiday Mode**: When ON, emails are paused

### Email Content
Each email includes:
- Personal greeting
- Today's timetable
- Events and announcements
- Lunch menu
- Important updates
- Professional formatting

---

## 🛠️ Troubleshooting

### Database Issues
**Problem**: "no such table: users"
**Solution**: Delete `app.db` and restart (it will auto-create)

### Email Not Sending
1. Check `GMAIL_USER` and `GMAIL_APP_PASSWORD` in `.env`
2. Verify you're using app-specific password (not regular Gmail password)
3. Enable 2-factor authentication on Gmail
4. Use admin panel "Send Test Email" to diagnose

### Scheduler Not Running
- Check `SCHEDULER_ENABLED=True` in `.env`
- Verify it's a weekday (Mon-Fri)
- Check if holiday mode is OFF
- Look for "Scheduler started" message on app startup

### Login Redirect Loops
- Clear browser cookies
- Check that SECRET_KEY is set in `.env`
- Verify user account exists in database

---

## 📊 System Requirements

- Python 3.7 or higher
- 100 MB disk space
- Internet connection (for Gmail SMTP)
- Modern web browser

---

## 🔒 Security Considerations

### Before Production Deployment
- ✅ Change `SECRET_KEY` to a random string
- ✅ Set `DEBUG=False`
- ✅ Use a strong `ADMIN_PASSWORD`
- ✅ Enable HTTPS
- ✅ Set up database backups
- ✅ Use Gmail app-specific passwords
- ✅ Review all environment variables
- ✅ Implement rate limiting
- ✅ Set up error logging
- ✅ Use a production WSGI server (gunicorn, etc.)

---

## 📝 Documentation

- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Detailed setup instructions
- **[IMPLEMENTATION_CHECKLIST.md](IMPLEMENTATION_CHECKLIST.md)** - Feature checklist
- **Code comments** - Throughout the codebase

---

## 🤝 Support

For issues or questions:
1. Check the [SETUP_GUIDE.md](SETUP_GUIDE.md)
2. Review error messages in browser console
3. Check Flask server console output
4. Verify all environment variables

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👨‍💻 Author

AS Updates Development Team

---

## 🎯 Roadmap

- [ ] SMS notifications
- [ ] Mobile app
- [ ] User groups/classes
- [ ] Custom email templates
- [ ] Integration with school management systems
- [ ] Multi-language support
- [ ] Dashboard analytics

---

## ✅ Version History

### v1.0 (Current)
- ✅ Complete authentication system
- ✅ User and admin dashboards
- ✅ Email scheduling
- ✅ Holiday mode
- ✅ Modern responsive UI
- ✅ Full documentation

---

**Happy using AS Updates! 🎉**

For the latest updates and documentation, visit the project repository.

Last Updated: May 18, 2024
