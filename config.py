import os
from dotenv import load_dotenv

load_dotenv()

# Flask settings
SECRET_KEY = os.getenv("SECRET_KEY", "dev-super-secret-key-change-in-production")
DEBUG = os.getenv("DEBUG", "False") == "True"

# Database settings
DATABASE = "app.db"

# Admin settings
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

# Email settings (Gmail SMTP)
GMAIL_USER = os.getenv("GMAIL_USER", "")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
EMAIL_ENCRYPTION_KEY = os.getenv("EMAIL_ENCRYPTION_KEY", "")

# Scheduler settings
SCHEDULER_ENABLED = os.getenv("SCHEDULER_ENABLED", "True") == "True"

# Timezone
TIMEZONE = os.getenv("TIMEZONE", "Europe/London")
