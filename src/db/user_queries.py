"""
User-related database queries with type hints.
"""

import sqlite3
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


def create_user(
    conn: sqlite3.Connection,
    username: str,
    password_hash: str
) -> Optional[Dict[str, Any]]:
    """Create a new user."""
    user_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    try:
        conn.execute('''
            INSERT INTO users (id, username, password_hash, is_active, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
        ''', (user_id, username, password_hash, now, now))
        conn.commit()
        return get_user_by_id(conn, user_id)
    except sqlite3.IntegrityError:
        logger.warning("Username already exists: %s", username)
        return None
    except Exception as e:
        logger.error("Failed to create user: %s", e)
        conn.rollback()
        return None


def get_user_by_id(conn: sqlite3.Connection, user_id: str) -> Optional[Dict[str, Any]]:
    """Get a user by ID."""
    cursor = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_user_by_username(conn: sqlite3.Connection, username: str) -> Optional[Dict[str, Any]]:
    """Get a user by username."""
    cursor = conn.execute('SELECT * FROM users WHERE username = ?', (username,))
    row = cursor.fetchone()
    return dict(row) if row else None


def update_user(
    conn: sqlite3.Connection,
    user_id: str,
    **updates: Any
) -> Optional[Dict[str, Any]]:
    """Update a user with the given fields."""
    if not updates:
        return get_user_by_id(conn, user_id)
    
    updates['updated_at'] = datetime.now().isoformat()
    
    set_clause = ', '.join(f'{key} = ?' for key in updates.keys())
    values = list(updates.values()) + [user_id]
    
    try:
        conn.execute(f'UPDATE users SET {set_clause} WHERE id = ?', values)
        conn.commit()
        return get_user_by_id(conn, user_id)
    except Exception as e:
        logger.error("Failed to update user %s: %s", user_id, e)
        conn.rollback()
        return None


def delete_user(conn: sqlite3.Connection, user_id: str) -> bool:
    """Delete a user by ID."""
    try:
        cursor = conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error("Failed to delete user %s: %s", user_id, e)
        conn.rollback()
        return False


def ensure_default_user(conn: sqlite3.Connection, default_user_id: str) -> Dict[str, Any]:
    """Ensure a default user exists and return it."""
    user = get_user_by_id(conn, default_user_id)
    if user:
        return user
    
    now = datetime.now().isoformat()
    try:
        conn.execute('''
            INSERT OR IGNORE INTO users (id, username, is_active, created_at, updated_at)
            VALUES (?, ?, 1, ?, ?)
        ''', (default_user_id, 'default', now, now))
        conn.commit()
        return get_user_by_id(conn, default_user_id) or {'id': default_user_id}
    except Exception as e:
        logger.error("Failed to create default user: %s", e)
        return {'id': default_user_id}


# Session management

def create_session(
    conn: sqlite3.Connection,
    user_id: str,
    expires_at: str
) -> Optional[str]:
    """Create a new session for a user."""
    session_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    try:
        conn.execute('''
            INSERT INTO sessions (session_id, user_id, expires_at, created_at)
            VALUES (?, ?, ?, ?)
        ''', (session_id, user_id, expires_at, now))
        conn.commit()
        return session_id
    except Exception as e:
        logger.error("Failed to create session: %s", e)
        conn.rollback()
        return None


def get_session(conn: sqlite3.Connection, session_id: str) -> Optional[Dict[str, Any]]:
    """Get a session by ID."""
    cursor = conn.execute('SELECT * FROM sessions WHERE session_id = ?', (session_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def delete_session(conn: sqlite3.Connection, session_id: str) -> bool:
    """Delete a session by ID."""
    try:
        cursor = conn.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error("Failed to delete session %s: %s", session_id, e)
        conn.rollback()
        return False


def cleanup_expired_sessions(conn: sqlite3.Connection) -> int:
    """Delete all expired sessions."""
    now = datetime.now().isoformat()
    try:
        cursor = conn.execute('DELETE FROM sessions WHERE expires_at < ?', (now,))
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        logger.error("Failed to cleanup expired sessions: %s", e)
        conn.rollback()
        return 0


# Settings management

def get_user_settings(conn: sqlite3.Connection, user_id: str) -> Optional[Dict[str, Any]]:
    """Get settings for a user."""
    cursor = conn.execute('SELECT * FROM settings WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def update_user_settings(
    conn: sqlite3.Connection,
    user_id: str,
    **settings: Any
) -> Optional[Dict[str, Any]]:
    """Update or create user settings."""
    now = datetime.now().isoformat()
    existing = get_user_settings(conn, user_id)
    
    try:
        if existing:
            settings['updated_at'] = now
            set_clause = ', '.join(f'{key} = ?' for key in settings.keys())
            values = list(settings.values()) + [user_id]
            conn.execute(f'UPDATE settings SET {set_clause} WHERE user_id = ?', values)
        else:
            settings['user_id'] = user_id
            settings['created_at'] = now
            settings['updated_at'] = now
            columns = ', '.join(settings.keys())
            placeholders = ', '.join('?' * len(settings))
            conn.execute(
                f'INSERT INTO settings ({columns}) VALUES ({placeholders})',
                list(settings.values())
            )
        conn.commit()
        return get_user_settings(conn, user_id)
    except Exception as e:
        logger.error("Failed to update settings for user %s: %s", user_id, e)
        conn.rollback()
        return None
