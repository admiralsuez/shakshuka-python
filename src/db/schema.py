"""
Database schema definitions and migrations.
"""

import sqlite3
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 15

# Table creation SQL statements
TABLES = {
    'users': '''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT UNIQUE,
            password_hash TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''',
    
    'tasks': '''
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            project TEXT,
            priority TEXT DEFAULT 'medium',
            status TEXT DEFAULT 'pending',
            completed BOOLEAN DEFAULT 0,
            completed_at TIMESTAMP,
            due_date TIMESTAMP,
            estimated_duration INTEGER DEFAULT 60,
            scheduled_hour INTEGER,
            scheduled_minute INTEGER,
            scheduled_date TEXT,
            scheduled_duration INTEGER,
            struck_forever BOOLEAN DEFAULT 0,
            struck_today BOOLEAN DEFAULT 0,
            struck_date TIMESTAMP,
            strike_report TEXT,
            strike_count INTEGER DEFAULT 0,
            daily_strikes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''',
    
    'notes': '''
        CREATE TABLE IF NOT EXISTS notes (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''',
    
    'settings': '''
        CREATE TABLE IF NOT EXISTS settings (
            user_id TEXT PRIMARY KEY,
            theme TEXT DEFAULT 'orange',
            dpi_scale INTEGER DEFAULT 100,
            autosave_interval INTEGER DEFAULT 30,
            notifications BOOLEAN DEFAULT 1,
            last_daily_reset_at TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''',
    
    'sessions': '''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''',
    
    'mobile_devices': '''
        CREATE TABLE IF NOT EXISTS mobile_devices (
            user_id TEXT NOT NULL,
            device_id TEXT NOT NULL,
            device_name TEXT,
            token_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_seen_at TEXT,
            PRIMARY KEY (user_id, device_id),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''',
    
    'mobile_inbox': '''
        CREATE TABLE IF NOT EXISTS mobile_inbox (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            device_id TEXT,
            device_name TEXT,
            payload_json TEXT,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            processed_at TEXT,
            result_json TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''',
    
    'migration_version': '''
        CREATE TABLE IF NOT EXISTS migration_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            description TEXT
        )
    ''',
    
    'settings_events': '''
        CREATE TABLE IF NOT EXISTS settings_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            setting_key TEXT NOT NULL,
            old_value TEXT,
            new_value TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    '''
}

# Index creation SQL statements
INDEXES = [
    'CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks (user_id)',
    'CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status)',
    'CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks (completed)',
    'CREATE INDEX IF NOT EXISTS idx_tasks_user_scheduled ON tasks (user_id, scheduled_date)',
    'CREATE INDEX IF NOT EXISTS idx_notes_user_id ON notes (user_id, updated_at DESC)',
    'CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id)',
    'CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions (expires_at)',
    'CREATE INDEX IF NOT EXISTS idx_mobile_devices_user_token ON mobile_devices (user_id, token_hash)',
    'CREATE INDEX IF NOT EXISTS idx_mobile_inbox_user_status_created ON mobile_inbox (user_id, status, created_at)',
    'CREATE INDEX IF NOT EXISTS idx_settings_events_user_timestamp ON settings_events (user_id, timestamp)',
]


def create_tables(conn: sqlite3.Connection) -> None:
    """Create all database tables."""
    conn.execute('PRAGMA foreign_keys = ON')
    conn.execute('PRAGMA journal_mode = WAL')
    
    for table_name, create_sql in TABLES.items():
        try:
            conn.execute(create_sql)
            logger.debug("Created table: %s", table_name)
        except Exception as e:
            logger.error("Failed to create table %s: %s", table_name, e)
            raise
    
    conn.commit()
    logger.info("All tables created successfully")


def create_indexes(conn: sqlite3.Connection) -> None:
    """Create all database indexes."""
    for index_sql in INDEXES:
        try:
            conn.execute(index_sql)
        except Exception as e:
            logger.warning("Failed to create index: %s", e)
    
    conn.commit()
    logger.info("Indexes created successfully")


def get_migration_version(conn: sqlite3.Connection) -> int:
    """Get current migration version from database."""
    try:
        cursor = conn.execute('SELECT version FROM migration_version ORDER BY version DESC LIMIT 1')
        result = cursor.fetchone()
        return result[0] if result else 0
    except sqlite3.OperationalError:
        conn.execute(TABLES['migration_version'])
        conn.execute('INSERT INTO migration_version (version, description) VALUES (0, "Initial version")')
        return 0


def set_migration_version(conn: sqlite3.Connection, version: int) -> None:
    """Update migration version in database."""
    conn.execute(
        'INSERT OR REPLACE INTO migration_version (version, description) VALUES (?, ?)',
        (version, f"Migration {version} applied")
    )


def run_migrations(conn: sqlite3.Connection) -> List[Dict[str, Any]]:
    """Run all pending database migrations."""
    migrations_applied: List[Dict[str, Any]] = []
    current_version = get_migration_version(conn)
    
    logger.info("Current migration version: %d", current_version)
    
    # Add migration functions here as needed
    # Each migration should check current_version and apply if needed
    
    if migrations_applied:
        new_version = max(m['version'] for m in migrations_applied)
        set_migration_version(conn, new_version)
        logger.info("Updated migration version to %d", new_version)
    
    return migrations_applied
