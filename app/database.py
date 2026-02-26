import sqlite3
import os

DB_PATH = os.environ.get("DB_PATH", "/app/data/hours.db")


def get_db():
    """Get a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """Initialize the database schema."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS time_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL UNIQUE,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            breaks TEXT NOT NULL DEFAULT '[]',
            total_hours REAL NOT NULL DEFAULT 0,
            overtime REAL NOT NULL DEFAULT 0,
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_date ON time_entries(date);

        CREATE TABLE IF NOT EXISTS adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hours REAL NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        INSERT OR IGNORE INTO settings (key, value) VALUES ('daily_target', '7.6');
    """)
    conn.commit()
    conn.close()


def get_setting(key: str, default: str = "") -> str:
    """Read a setting value from the database."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def set_setting(key: str, value: str) -> None:
    """Upsert a setting value in the database."""
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()
