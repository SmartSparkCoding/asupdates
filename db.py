import json
import os
import sqlite3

from config import DATABASE


TIMETABLE_PERIODS = [str(period) for period in range(1, 8)]


def _default_timetable():
    return {period: {"subject": "", "room": ""} for period in TIMETABLE_PERIODS}


def _ensure_column(conn, table, column, definition):
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if column not in existing_columns:
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _ensure_settings_row(conn):
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM settings WHERE id=1")
    if cursor.fetchone() is None:
        cursor.execute(
            """
            INSERT INTO settings (id, holiday_mode, holiday_weeks, ab_week, menu_week, menu_week_1, menu_week_2, menu_week_3, school_notice)
            VALUES (1, 0, 0, 'A', 1, '', '', '', '')
            """
        )


def _ensure_user_defaults(conn):
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET name = COALESCE(name, ''), timetable_a = COALESCE(timetable_a, ''), timetable_b = COALESCE(timetable_b, '')")
    conn.commit()

def get_db():
    """Get database connection with row factory."""
    if not os.path.exists(DATABASE):
        init_db()
    
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize database with proper schema."""
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    
    try:
        # Enable foreign keys
        c.execute("PRAGMA foreign_keys = ON")

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT DEFAULT '',
                pin TEXT,
                send_emails INTEGER DEFAULT 1,
                timetable_a TEXT DEFAULT '',
                timetable_b TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                holiday_mode INTEGER DEFAULT 0,
                holiday_weeks INTEGER DEFAULT 0,
                ab_week TEXT DEFAULT 'A',
                menu_week INTEGER DEFAULT 1,
                menu_week_1 TEXT DEFAULT '',
                menu_week_2 TEXT DEFAULT '',
                menu_week_3 TEXT DEFAULT '',
                school_notice TEXT DEFAULT ''
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS school_notice_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notice_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        c.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")

        _ensure_settings_row(conn)
        
        conn.commit()
        print("[✓] Database initialized successfully")
        
    except Exception as e:
        print(f"[✗] Database initialization error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def verify_schema():
    """Verify database schema is correct."""
    try:
        conn = get_db()
        c = conn.cursor()

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                name TEXT DEFAULT '',
                pin TEXT,
                send_emails INTEGER DEFAULT 1,
                timetable_a TEXT DEFAULT '',
                timetable_b TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                id INTEGER PRIMARY KEY,
                holiday_mode INTEGER DEFAULT 0,
                holiday_weeks INTEGER DEFAULT 0,
                ab_week TEXT DEFAULT 'A',
                menu_week INTEGER DEFAULT 1,
                menu_week_1 TEXT DEFAULT '',
                menu_week_2 TEXT DEFAULT '',
                menu_week_3 TEXT DEFAULT ''
            )
            """
        )

        _ensure_column(conn, "users", "name", "TEXT DEFAULT ''")
        _ensure_column(conn, "users", "timetable_a", "TEXT DEFAULT ''")
        _ensure_column(conn, "users", "timetable_b", "TEXT DEFAULT ''")
        _ensure_column(conn, "users", "day_timetable", "TEXT DEFAULT ''")
        _ensure_column(conn, "settings", "holiday_weeks", "INTEGER DEFAULT 0")
        _ensure_column(conn, "settings", "menu_week", "INTEGER DEFAULT 1")
        _ensure_column(conn, "settings", "menu_week_1", "TEXT DEFAULT ''")
        _ensure_column(conn, "settings", "menu_week_2", "TEXT DEFAULT ''")
        _ensure_column(conn, "settings", "menu_week_3", "TEXT DEFAULT ''")
        _ensure_column(conn, "settings", "school_notice", "TEXT DEFAULT ''")
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS school_notice_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notice_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        _ensure_settings_row(conn)
        _ensure_user_defaults(conn)

        conn.commit()

        conn.close()
        return True
        
    except Exception as e:
        print(f"[!] Schema verification error: {e}")
        init_db()
        return False
