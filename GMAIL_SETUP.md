# Gmail Setup & Email Features Guide

## 📧 Email Template Location

The email template is located at:
```
/workspaces/asupdates/templates/email.html
```

This is the HTML template used by the scheduler to generate personalized emails. **No additional setup needed** - it's already integrated.

---

## 🔗 Gmail Configuration

### Step 1: Enable 2-Factor Authentication
1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Click **2-Step Verification**
3. Follow the setup process

### Step 2: Create Gmail App Password
1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Select **Mail** and **Windows Computer** (or your device type)
3. Google will generate a 16-character password with spaces
4. Copy this password

### Step 3: Configure .env File
Create or update your `.env` file in the root directory:

```env
GMAIL_USER=your.email@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

**Example:**
```env
GMAIL_USER=john.smith@gmail.com
GMAIL_APP_PASSWORD=abcd efgh ijkl mnop
```

### Step 4: Verify Configuration
Once configured, test by:
1. Go to Admin Dashboard
2. Click **Send Test Email** button
3. Check your inbox (or spam folder)

---

## 🚀 New Feature: Send Email to Individual Users

### What It Does
Admins can now send an email to any user **immediately**, bypassing:
- ❌ Time schedule (doesn't wait until 8 AM)
- ❌ Holiday mode (sends even if holidays are on)
- ❌ Email toggle (sends regardless of send_emails setting)

### How to Use
1. Go to **Admin Dashboard**
2. In the **User Management** table, find the user
3. Click the **Email** button (blue) next to the user
4. The email is sent immediately
5. You'll see a success or error message

### What Email Is Sent
- Subject: "School Update - Manual Send"
- Content: Same as the scheduled email (from `templates/email.html`)
- Personalizations: User's email address is included

### Useful For
- Testing email configuration
- Sending urgent updates to specific users
- Debugging email delivery issues
- Manual notifications outside the 8 AM schedule

---

## 📝 Email Template Customization

If you want to customize the email design, edit:
```
templates/email.html
```

The template supports these variables (used by `scheduler.py`):
- `{{ user_email }}` - User's email address (auto-inserted)
- `{{ current_date }}` - Current date
- `{{ timetable }}` - School timetable
- `{{ lunch }}` - Lunch menu
- `{{ events }}` - Today's events
- `{{ updates }}` - System updates

---

## ✅ Troubleshooting

### Email Not Sending?
1. Check `.env` file has correct Gmail credentials
2. Verify Gmail 2-Factor Authentication is enabled
3. Click "Send Test Email" to debug
4. Check console output for error messages

### "Failed to send email" Error
- Invalid Gmail credentials
- Gmail 2-Factor not enabled
- App password not created correctly (ensure you're using the 16-char password)
- Network connectivity issue

### Email Goes to Spam
- This is normal for automated emails
- Ask users to mark emails as "Not Spam"
- Gmail sender reputation builds over time
- Consider using a school Gmail account instead of personal

---

## 🔐 Security Notes

- **NEVER** commit `.env` file to git
- **NEVER** put plaintext passwords in code
- Use environment variables for ALL credentials
- Rotate app passwords periodically
- Keep `.env` on production server only

---

## 📅 Scheduler Information

The automatic scheduler:
- Runs **every weekday (Mon-Fri)** at **08:00 UK time**
- Uses the same email template as manual sends
- Respects **Holiday Mode** setting (can be toggled in Admin Dashboard)
- Respects **individual user email toggle** (Email On/Off per user)

---

## Quick Reference

| Feature | Location | When Runs |
|---------|----------|-----------|
| Auto Emails | Scheduler | 08:00 Mon-Fri (unless holiday mode) |
| Manual Send | Admin Dashboard > User > Email button | Immediately, anytime |
| Test Email | Admin Dashboard > Test Email section | Immediately |
| Email Template | `templates/email.html` | Used for all emails |

---

**Configuration Complete?** Your system is ready to send emails! 🎉
