import sqlite3
from config import DATABASE


def get_db():
    return sqlite3.connect(DATABASE)


def init_db():
    db = get_db()
    c = db.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE,
        pin TEXT,
        send_emails INTEGER DEFAULT 1,
        week_group TEXT DEFAULT 'A'
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        id INTEGER PRIMARY KEY,
        week_type TEXT DEFAULT 'A',
        holiday_mode INTEGER DEFAULT 0,
        custom_message TEXT DEFAULT ''
    )
    """)

    c.execute("INSERT OR IGNORE INTO settings (id) VALUES (1)")

    db.commit()
    db.close()
