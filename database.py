import sqlite3

DB_NAME = "data.db"

def get_db():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        timetable_group TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    c.execute("""
    INSERT OR IGNORE INTO settings (key, value) VALUES ('week_type', 'A')
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS skip_dates (
        date TEXT PRIMARY KEY
    )
    """)

    conn.commit()
    conn.close()
