import os

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")

DATABASE = "data.db"

EMAIL_FROM = os.getenv("EMAIL_FROM", "")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD", "")
