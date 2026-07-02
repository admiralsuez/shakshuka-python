"""
User repository for user account and settings operations.
Extracted from sqlite_data_manager.py for modularity and testing.
"""

import logging
from typing import Any, Dict, Optional

from src.constants import DEFAULT_USER_ID
from src.exceptions import DatabaseError


logger = logging.getLogger(__name__)


class UserRepository:
    """
    Repository for user account and settings operations.
    Handles user creation, verification, and settings management.
    """

    def __init__(self, get_connection, logger=None):
        """
        Initialize repository with database connection.
        
        Args:
            get_connection: Function to get a database connection
            logger: Logger instance (optional)
        """
        self.get_connection = get_connection
        self.logger = logger or globals()["logger"]

    def ensure_user_exists(self, user_id: str) -> bool:
        """
        Ensure user exists in database, create if not exists.
        
        For the default user, creates with placeholder credentials.
        For other users, creates with optional password hash.
        """
        try:
            with self.get_connection() as conn:
                # Check if user exists
                cursor = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,))
                if cursor.fetchone():
                    return True

                # Create user if not exists (single-user mode uses DEFAULT_USER_ID)
                if user_id == DEFAULT_USER_ID:
                    # For the default user, use a placeholder password hash
                    password_hash = f"{DEFAULT_USER_ID}_no_password"
                else:
                    password_hash = None

                conn.execute(
                    """
                    INSERT INTO users (id, username, password_hash, is_active)
                    VALUES (?, ?, ?, ?)
                """,
                    (user_id, f"user_{user_id[:8]}", password_hash, 1),
                )

                # Create default settings for user
                conn.execute(
                    """
                    INSERT INTO settings (user_id, theme, dpi_scale, autosave_interval, notifications)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (user_id, "orange", 100, 30, 1),
                )

                conn.commit()
                self.logger.info(f"Created user: {user_id}")
                return True

        except Exception as e:
            self.logger.error(f"Error ensuring user exists {user_id}: {e}")
            return False

    def user_exists(self, user_id: str) -> bool:
        """Check if a user exists in the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,))
                return cursor.fetchone() is not None
        except Exception as e:
            self.logger.error(f"Error checking if user exists {user_id}: {e}")
            return False

    def get_user_settings(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user settings"""
        try:
            self.ensure_user_exists(user_id)
            
            with self.get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT * FROM settings WHERE user_id = ?
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()
                
                if not row:
                    return None
                
                return dict(row)
        except Exception as e:
            self.logger.error(f"Error getting user settings for {user_id}: {e}")
            raise DatabaseError(
                message=f"Error getting user settings for {user_id}",
                cause=e
            )

    def update_user_settings(
        self, user_id: str, settings: Dict[str, Any]
    ) -> bool:
        """Update user settings"""
        try:
            self.ensure_user_exists(user_id)

            with self.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                
                try:
                    # Build dynamic UPDATE query from provided settings
                    valid_fields = [
                        "theme", "dpi_scale", "autosave_interval", "notifications",
                        "daily_reset_time", "compact_mode", "intensity", "last_daily_reset_at"
                    ]
                    
                    update_fields = []
                    values = []
                    
                    for key, value in settings.items():
                        if key in valid_fields:
                            update_fields.append(f"{key} = ?")
                            values.append(value)
                    
                    if not update_fields:
                        conn.rollback()
                        return True  # No fields to update
                    
                    values.append(user_id)
                    update_sql = f"UPDATE settings SET {', '.join(update_fields)} WHERE user_id = ?"
                    
                    conn.execute(update_sql, values)
                    conn.commit()
                    
                    self.logger.info(f"Updated settings for user {user_id}")
                    return True
                
                except Exception as inner_e:
                    conn.rollback()
                    self.logger.error(f"Transaction failed for user {user_id}: {inner_e}")
                    raise
        
        except Exception as e:
            self.logger.error(f"Error updating user settings for {user_id}: {e}")
            raise DatabaseError(
                message=f"Error updating user settings for {user_id}",
                cause=e
            )

    def get_setting(self, user_id: str, setting_key: str) -> Optional[Any]:
        """Get a specific setting value for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    f"SELECT {setting_key} FROM settings WHERE user_id = ?",
                    (user_id,),
                )
                row = cursor.fetchone()
                
                if row:
                    return row[0]
                return None
        except Exception as e:
            self.logger.error(f"Error getting setting {setting_key} for user {user_id}: {e}")
            return None

    def set_setting(self, user_id: str, setting_key: str, value: Any) -> bool:
        """Set a specific setting value for a user"""
        try:
            self.ensure_user_exists(user_id)
            
            valid_fields = [
                "theme", "dpi_scale", "autosave_interval", "notifications",
                "daily_reset_time", "compact_mode", "intensity", "last_daily_reset_at"
            ]
            
            if setting_key not in valid_fields:
                self.logger.warning(f"Invalid setting key: {setting_key}")
                return False
            
            with self.get_connection() as conn:
                conn.execute(
                    f"UPDATE settings SET {setting_key} = ? WHERE user_id = ?",
                    (value, user_id),
                )
                conn.commit()
                self.logger.info(f"Set {setting_key} = {value} for user {user_id}")
                return True
        
        except Exception as e:
            self.logger.error(f"Error setting {setting_key} for user {user_id}: {e}")
            return False

    def get_all_users(self) -> Optional[list]:
        """Get all users in the database"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute("SELECT * FROM users WHERE is_active = 1")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except Exception as e:
            self.logger.error(f"Error getting all users: {e}")
            raise DatabaseError(
                message="Error getting all users",
                cause=e
            )

    def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user account"""
        try:
            with self.get_connection() as conn:
                conn.execute(
                    "UPDATE users SET is_active = 0 WHERE id = ?",
                    (user_id,),
                )
                conn.commit()
                self.logger.info(f"Deactivated user: {user_id}")
                return True
        except Exception as e:
            self.logger.error(f"Error deactivating user {user_id}: {e}")
            return False

    def reactivate_user(self, user_id: str) -> bool:
        """Reactivate a user account"""
        try:
            with self.get_connection() as conn:
                conn.execute(
                    "UPDATE users SET is_active = 1 WHERE id = ?",
                    (user_id,),
                )
                conn.commit()
                self.logger.info(f"Reactivated user: {user_id}")
                return True
        except Exception as e:
            self.logger.error(f"Error reactivating user {user_id}: {e}")
            return False

    def update_user_heartbeat(self, user_id: str) -> bool:
        """Update the last seen timestamp for a user"""
        try:
            self.ensure_user_exists(user_id)
            
            with self.get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO user_heartbeat (user_id, last_seen_at)
                    VALUES (?, CURRENT_TIMESTAMP)
                    """,
                    (user_id,),
                )
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"Error updating user heartbeat for {user_id}: {e}")
            return False

    def get_last_seen(self, user_id: str) -> Optional[str]:
        """Get the last seen timestamp for a user"""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT last_seen_at FROM user_heartbeat WHERE user_id = ?",
                    (user_id,),
                )
                row = cursor.fetchone()
                return row[0] if row else None
        except Exception as e:
            self.logger.error(f"Error getting last seen for user {user_id}: {e}")
            return None
