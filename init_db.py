import sqlite3

conn = sqlite3.connect("database.db")
c = conn.cursor()

# USERS TABLE
c.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE,
    pin_hash TEXT,
    is_admin INTEGER DEFAULT 0,
    send_emails INTEGER DEFAULT 1
)
""")

# HOLIDAYS TABLE
c.execute("""
CREATE TABLE IF NOT EXISTS holidays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE
)
""")

conn.commit()
conn.close()

print("Database initialised.")
