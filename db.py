import sqlite3
from config import DATABASE

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    c = db.cursor()

    # USERS
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        pin TEXT,
        send_emails INTEGER DEFAULT 1
    )
    """)

    # SETTINGS
    c.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY,
        holiday_mode INTEGER DEFAULT 0,
        week_type TEXT DEFAULT 'A'
    )
    """)

    c.execute("INSERT OR IGNORE INTO settings (id) VALUES (1)")

    db.commit()
    db.close()
