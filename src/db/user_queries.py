"""
User-related database queries with type hints.
"""

import sqlite3
import uuid
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from src.exceptions import DatabaseError, ValidationError

logger = logging.getLogger(__name__)


def create_user(
    conn: sqlite3.Connection,
    username: str,
    password_hash: str
) -> Optional[Dict[str, Any]]:
    """Create a new user."""
    if not username or not isinstance(username, str):
        raise ValidationError(message="Invalid username")
    if not password_hash or not isinstance(password_hash, str):
        raise ValidationError(message="Invalid password hash")
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
        raise ValidationError(message="Username already exists")
    except Exception as e:
        logger.exception("Failed to create user")
        try:
            conn.rollback()
        except Exception:  # noqa: broad-except - Data layer defensive exception handling
            logger.exception("Rollback failed during create_user")
        raise DatabaseError(message="Failed to create user", cause=e)


def get_user_by_id(conn: sqlite3.Connection, user_id: str) -> Optional[Dict[str, Any]]:
    """Get a user by ID."""
    if not user_id or not isinstance(user_id, str):
        raise ValidationError(message="Invalid user_id")
    try:
        cursor = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.exception("Failed to get user by id")
        raise DatabaseError(message="Failed to get user by id", details={'user_id': user_id}, cause=e)


def get_user_by_username(conn: sqlite3.Connection, username: str) -> Optional[Dict[str, Any]]:
    """Get a user by username."""
    if not username or not isinstance(username, str):
        raise ValidationError(message="Invalid username")
    try:
        cursor = conn.execute('SELECT * FROM users WHERE username = ?', (username,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.exception("Failed to get user by username")
        raise DatabaseError(message="Failed to get user by username", details={'username': username}, cause=e)


def update_user(
    conn: sqlite3.Connection,
    user_id: str,
    **updates: Any
) -> Optional[Dict[str, Any]]:
    """Update a user with the given fields."""
    if not user_id or not isinstance(user_id, str):
        raise ValidationError(message="Invalid user_id")
    if not updates:
        return get_user_by_id(conn, user_id)

    allowed_fields = {'username', 'password_hash', 'is_active'}
    for key in list(updates.keys()):
        if key not in allowed_fields:
            raise ValidationError(message="Invalid update field", details={'field': key})
    
    updates['updated_at'] = datetime.now().isoformat()
    
    set_clause = ', '.join(f'{key} = ?' for key in updates.keys())
    values = list(updates.values()) + [user_id]
    
    try:
        conn.execute(f'UPDATE users SET {set_clause} WHERE id = ?', values)
        conn.commit()
        return get_user_by_id(conn, user_id)
    except Exception as e:
        logger.exception("Failed to update user %s", user_id)
        try:
            conn.rollback()
        except Exception:  # noqa: broad-except - Data layer defensive exception handling
            logger.exception("Rollback failed during update_user")
        raise DatabaseError(message="Failed to update user", details={'user_id': user_id}, cause=e)


def delete_user(conn: sqlite3.Connection, user_id: str) -> bool:
    """Delete a user by ID."""
    if not user_id or not isinstance(user_id, str):
        raise ValidationError(message="Invalid user_id")
    try:
        cursor = conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.exception("Failed to delete user %s", user_id)
        try:
            conn.rollback()
        except Exception:  # noqa: broad-except - Data layer defensive exception handling
            logger.exception("Rollback failed during delete_user")
        raise DatabaseError(message="Failed to delete user", details={'user_id': user_id}, cause=e)


def ensure_default_user(conn: sqlite3.Connection, default_user_id: str) -> Dict[str, Any]:
    """Ensure a default user exists and return it."""
    if not default_user_id or not isinstance(default_user_id, str):
        raise ValidationError(message="Invalid default_user_id")
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
        user = get_user_by_id(conn, default_user_id)
        if not user:
            raise DatabaseError(message="Failed to ensure default user", details={'user_id': default_user_id})
        return user
    except Exception as e:
        logger.exception("Failed to ensure default user")
        raise DatabaseError(message="Failed to ensure default user", details={'user_id': default_user_id}, cause=e)


# Session management

def create_session(
    conn: sqlite3.Connection,
    user_id: str,
    expires_at: str
) -> Optional[str]:
    """Create a new session for a user."""
    if not user_id or not isinstance(user_id, str):
        raise ValidationError(message="Invalid user_id")
    if not expires_at or not isinstance(expires_at, str):
        raise ValidationError(message="Invalid expires_at")
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
        logger.exception("Failed to create session")
        try:
            conn.rollback()
        except Exception:  # noqa: broad-except - Data layer defensive exception handling
            logger.exception("Rollback failed during create_session")
        raise DatabaseError(message="Failed to create session", details={'user_id': user_id}, cause=e)


def get_session(conn: sqlite3.Connection, session_id: str) -> Optional[Dict[str, Any]]:
    """Get a session by ID."""
    if not session_id or not isinstance(session_id, str):
        raise ValidationError(message="Invalid session_id")
    try:
        cursor = conn.execute('SELECT * FROM sessions WHERE session_id = ?', (session_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.exception("Failed to get session")
        raise DatabaseError(message="Failed to get session", details={'session_id': session_id}, cause=e)


def delete_session(conn: sqlite3.Connection, session_id: str) -> bool:
    """Delete a session by ID."""
    if not session_id or not isinstance(session_id, str):
        raise ValidationError(message="Invalid session_id")
    try:
        cursor = conn.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.exception("Failed to delete session %s", session_id)
        try:
            conn.rollback()
        except Exception:  # noqa: broad-except - Data layer defensive exception handling
            logger.exception("Rollback failed during delete_session")
        raise DatabaseError(message="Failed to delete session", details={'session_id': session_id}, cause=e)


def cleanup_expired_sessions(conn: sqlite3.Connection) -> int:
    """Delete all expired sessions."""
    now = datetime.now().isoformat()
    try:
        cursor = conn.execute('DELETE FROM sessions WHERE expires_at < ?', (now,))
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        logger.exception("Failed to cleanup expired sessions")
        try:
            conn.rollback()
        except Exception:  # noqa: broad-except - Data layer defensive exception handling
            logger.exception("Rollback failed during cleanup_expired_sessions")
        raise DatabaseError(message="Failed to cleanup expired sessions", cause=e)


# Settings management

def get_user_settings(conn: sqlite3.Connection, user_id: str) -> Optional[Dict[str, Any]]:
    """Get settings for a user."""
    if not user_id or not isinstance(user_id, str):
        raise ValidationError(message="Invalid user_id")
    try:
        cursor = conn.execute('SELECT * FROM settings WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.exception("Failed to get user settings")
        raise DatabaseError(message="Failed to get user settings", details={'user_id': user_id}, cause=e)


def update_user_settings(
    conn: sqlite3.Connection,
    user_id: str,
    **settings: Any
) -> Optional[Dict[str, Any]]:
    """Update or create user settings."""
    if not user_id or not isinstance(user_id, str):
        raise ValidationError(message="Invalid user_id")
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
        logger.exception("Failed to update settings for user %s", user_id)
        try:
            conn.rollback()
        except Exception:  # noqa: broad-except - Data layer defensive exception handling
            logger.exception("Rollback failed during update_user_settings")
        raise DatabaseError(message="Failed to update settings", details={'user_id': user_id}, cause=e)
