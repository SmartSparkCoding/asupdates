import json
import os
import sqlite3

from config import DATABASE
from email_security import migrate_user_emails


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


def _ensure_mailing_lists_defaults(conn):
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE mailing_lists
        SET name = COALESCE(name, ''),
            description = COALESCE(description, ''),
            email_mode = COALESCE(email_mode, 'premade'),
            title = COALESCE(title, ''),
            subject = COALESCE(subject, ''),
            body_text = COALESCE(body_text, ''),
            signature_text = COALESCE(signature_text, ''),
            manual_html = COALESCE(manual_html, ''),
            footer_html = COALESCE(footer_html, '')
        """
    )


def _ensure_user_defaults(conn):
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET name = COALESCE(name, ''), timetable_a = COALESCE(timetable_a, ''), timetable_b = COALESCE(timetable_b, ''), homework_in_email = COALESCE(homework_in_email, 1)")
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
                email_lookup TEXT UNIQUE DEFAULT '',
                name TEXT DEFAULT '',
                pin TEXT,
                send_emails INTEGER DEFAULT 1,
                timetable_a TEXT DEFAULT '',
                timetable_b TEXT DEFAULT '',
                homework_in_email INTEGER DEFAULT 1,
                email_send_time TEXT DEFAULT '08:00',
                timezone TEXT DEFAULT 'Europe/London',
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

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS homework_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                title TEXT NOT NULL,
                details TEXT DEFAULT '',
                due_date TEXT NOT NULL,
                due_time TEXT DEFAULT '23:59',
                completed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS active_sessions (
                session_key TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                is_admin INTEGER DEFAULT 0,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS mailing_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                email_mode TEXT DEFAULT 'premade',
                title TEXT DEFAULT '',
                subject TEXT DEFAULT '',
                body_text TEXT DEFAULT '',
                signature_text TEXT DEFAULT '',
                manual_html TEXT DEFAULT '',
                footer_html TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS mailing_list_members (
                list_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (list_id, user_id),
                FOREIGN KEY (list_id) REFERENCES mailing_lists(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS mailing_list_sends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                email_mode TEXT DEFAULT 'premade',
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (list_id) REFERENCES mailing_lists(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        c.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lookup ON users(email_lookup)")

        _ensure_settings_row(conn)
        migrate_user_emails(conn)
        
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
                email_lookup TEXT UNIQUE DEFAULT '',
                name TEXT DEFAULT '',
                pin TEXT,
                send_emails INTEGER DEFAULT 1,
                timetable_a TEXT DEFAULT '',
                timetable_b TEXT DEFAULT '',
                homework_in_email INTEGER DEFAULT 1,
                email_send_time TEXT DEFAULT '08:00',
                timezone TEXT DEFAULT 'Europe/London',
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
        _ensure_column(conn, "users", "email_lookup", "TEXT DEFAULT ''")
        _ensure_column(conn, "users", "timetable_a", "TEXT DEFAULT ''")
        _ensure_column(conn, "users", "timetable_b", "TEXT DEFAULT ''")
        _ensure_column(conn, "users", "homework_in_email", "INTEGER DEFAULT 1")
        _ensure_column(conn, "users", "day_timetable", "TEXT DEFAULT ''")
        _ensure_column(conn, "users", "email_send_time", "TEXT DEFAULT '08:00'")
        _ensure_column(conn, "users", "timezone", "TEXT DEFAULT 'Europe/London'")
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

        _ensure_column(conn, "mailing_lists", "description", "TEXT DEFAULT ''")
        _ensure_column(conn, "mailing_lists", "email_mode", "TEXT DEFAULT 'premade'")
        _ensure_column(conn, "mailing_lists", "title", "TEXT DEFAULT ''")
        _ensure_column(conn, "mailing_lists", "subject", "TEXT DEFAULT ''")
        _ensure_column(conn, "mailing_lists", "body_text", "TEXT DEFAULT ''")
        _ensure_column(conn, "mailing_lists", "signature_text", "TEXT DEFAULT ''")
        _ensure_column(conn, "mailing_lists", "manual_html", "TEXT DEFAULT ''")
        _ensure_column(conn, "mailing_lists", "footer_html", "TEXT DEFAULT ''")
        _ensure_column(conn, "mailing_lists", "updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP")

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS mailing_lists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                email_mode TEXT DEFAULT 'premade',
                title TEXT DEFAULT '',
                subject TEXT DEFAULT '',
                body_text TEXT DEFAULT '',
                signature_text TEXT DEFAULT '',
                manual_html TEXT DEFAULT '',
                footer_html TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS mailing_list_members (
                list_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (list_id, user_id),
                FOREIGN KEY (list_id) REFERENCES mailing_lists(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS mailing_list_sends (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                list_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                email_mode TEXT DEFAULT 'premade',
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (list_id) REFERENCES mailing_lists(id) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS homework_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                title TEXT NOT NULL,
                details TEXT DEFAULT '',
                due_date TEXT NOT NULL,
                due_time TEXT DEFAULT '23:59',
                completed INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        c.execute(
            """
            CREATE TABLE IF NOT EXISTS active_sessions (
                session_key TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                is_admin INTEGER DEFAULT 0,
                last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        _ensure_settings_row(conn)
        _ensure_user_defaults(conn)
        _ensure_mailing_lists_defaults(conn)
        migrate_user_emails(conn)
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_lookup ON users(email_lookup)")

        conn.commit()

        conn.close()
        return True
        
    except Exception as e:
        print(f"[!] Schema verification error: {e}")
        init_db()
        return False
