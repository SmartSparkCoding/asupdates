import sqlite3
import os
from datetime import datetime
from config import DATABASE

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
        
        # Drop existing tables if they exist (clean slate)
        c.execute("DROP TABLE IF EXISTS users")
        c.execute("DROP TABLE IF EXISTS settings")
        
        # Create users table
        c.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            pin TEXT,
            send_emails INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        # Create settings table
        c.execute("""
        CREATE TABLE settings (
            id INTEGER PRIMARY KEY,
            holiday_mode INTEGER DEFAULT 0,
            ab_week TEXT DEFAULT 'A'
        )
        """)
        
        # Insert default settings
        c.execute("""
        INSERT INTO settings (id, holiday_mode, ab_week)
        VALUES (1, 0, 'A')
        """)
        
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
        
        # Check users table
        c.execute("PRAGMA table_info(users)")
        users_cols = {row[1] for row in c.fetchall()}
        required_users = {"id", "email", "pin", "send_emails", "created_at"}
        
        # Check settings table
        c.execute("PRAGMA table_info(settings)")
        settings_cols = {row[1] for row in c.fetchall()}
        required_settings = {"id", "holiday_mode", "ab_week"}
        
        conn.close()
        
        users_ok = required_users.issubset(users_cols)
        settings_ok = required_settings.issubset(settings_cols)
        
        if not users_ok or not settings_ok:
            print("[!] Schema mismatch detected - reinitializing...")
            init_db()
            return False
        
        return True
        
    except Exception as e:
        print(f"[!] Schema verification error: {e}")
        init_db()
        return False
