"""Data manager coordinator for Shakshuka task management application.

Composes repository classes to provide a unified data access layer.
Maintains backward compatibility with the monolithic SQLiteDataManager API.
"""

import logging
import os
import sqlite3
import sys
import threading
import time
from contextlib import contextmanager
from queue import Empty, Full, Queue
from typing import Any, Callable, Dict, List, Optional

from src.constants import (
    DB_CONNECTION_TIMEOUT,
    DB_POOL_WAIT_TIMEOUT,
    DEFAULT_USER_ID,
)
from src.exceptions import DatabaseError, ValidationError

# Import repository classes
from .analytics_repository import AnalyticsRepository
from .archive_repository import ArchiveRepository
from .migrations_handler import MigrationsHandler
from .note_repository import NoteRepository
from .strike_repository import StrikeRepository
from .task_repository import TaskRepository
from .user_repository import UserRepository

logger = logging.getLogger(__name__)


class DataManager:
    """Coordinator for all data repositories with backward-compatible API.
    
    Manages database connection pool and delegates operations to specialized
    repository classes. Maintains all public APIs from original SQLiteDataManager.
    """

    def __init__(self, data_dir: str = "data", pool_size: int = 5):
        """Initialize DataManager with connection pool and repositories.
        
        Args:
            data_dir: Directory for database files
            pool_size: Number of database connections in pool
        """
        # Handle PyInstaller bundle path
        if getattr(sys, "frozen", False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))

        self.data_dir = os.path.join(base_path, data_dir)
        self.db_path = os.path.join(self.data_dir, "shakshuka.db")

        # Thread safety
        self._lock = threading.RLock()

        # Connection pool
        self._pool_size = pool_size
        self._connection_pool = Queue(maxsize=pool_size)
        self._pool_get_count = 0
        self._pool_timeout_count = 0
        self._pool_return_count = 0
        self._pool_high_watermark_in_use = 0

        # Create data directory if it doesn't exist
        try:
            os.makedirs(self.data_dir, exist_ok=True)
        except Exception as e:
            raise DatabaseError(
                message=f"Failed to create data directory '{self.data_dir}'",
                cause=e,
            )

        # Setup logging
        self.logger = logger
        self.logger.info("Data directory ensured: %s", os.path.abspath(self.data_dir))

        # Initialize connection pool
        self._init_connection_pool()

        # Initialize database schema
        self._init_database()

        # Initialize repositories
        self._init_repositories()

    def _init_connection_pool(self):
        """Initialize connection pool."""
        try:
            for _ in range(self._pool_size):
                conn = sqlite3.connect(
                    self.db_path, timeout=DB_CONNECTION_TIMEOUT, check_same_thread=False
                )
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA journal_mode = WAL")
                conn.row_factory = sqlite3.Row
                self._connection_pool.put(conn)
            self.logger.info("Connection pool initialized with %d connections", self._pool_size)
        except Exception as e:
            self.logger.exception("Failed to initialize connection pool")
            raise DatabaseError(message="Failed to initialize connection pool", cause=e)

    def _get_pooled_connection(self):
        """Get connection from pool with timeout."""
        start = time.monotonic()
        in_use = None
        try:
            conn = self._connection_pool.get(timeout=DB_POOL_WAIT_TIMEOUT)
            self._pool_get_count += 1
            try:
                in_use = self._pool_size - self._connection_pool.qsize()
                if in_use > self._pool_high_watermark_in_use:
                    self._pool_high_watermark_in_use = in_use
            except Exception:  # noqa: broad-except
                in_use = None
            waited = time.monotonic() - start
            if waited >= max(0.5, DB_POOL_WAIT_TIMEOUT * 0.5):
                self.logger.warning(
                    "Waited %.3fs for pooled DB connection (in_use=%s)", waited, in_use
                )
            return conn
        except Empty:
            self._pool_timeout_count += 1
            try:
                stats = self.get_pool_stats()
            except Exception:  # noqa: broad-except
                stats = None
            self.logger.error(
                "Connection pool exhausted (wait_timeout=%.3fs) stats=%s",
                DB_POOL_WAIT_TIMEOUT,
                stats,
            )
            raise DatabaseError(
                message="Connection pool exhausted - timeout waiting for connection"
            )

    def _return_connection(self, conn):
        """Return connection to pool."""
        try:
            if conn:
                self._connection_pool.put(conn, block=False)
                self._pool_return_count += 1
        except Full:
            self.logger.error(
                "Connection pool full while returning connection; closing returned connection"
            )
            try:
                conn.close()
            except Exception:  # noqa: broad-except
                self.logger.exception("Failed to close connection after pool full")
        except Exception:  # noqa: broad-except
            self.logger.exception("Failed to return connection to pool")
            try:
                conn.close()
            except Exception:  # noqa: broad-except
                self.logger.exception("Failed to close connection after return failure")

    @contextmanager
    def pooled_connection(self):
        """Context manager for pooled database connection."""
        conn = self._get_pooled_connection()
        try:
            yield conn
        finally:
            try:
                conn.rollback()
            except Exception:  # noqa: broad-except
                self.logger.exception("Failed to rollback pooled DB connection")
            try:
                self._return_connection(conn)
            except Exception:  # noqa: broad-except
                self.logger.exception("Failed to return pooled DB connection")

    def get_pool_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        try:
            available = self._connection_pool.qsize()
        except Exception:  # noqa: broad-except
            available = None
        in_use = None
        try:
            if isinstance(available, int):
                in_use = self._pool_size - available
        except Exception:  # noqa: broad-except
            in_use = None

        return {
            "pool_size": self._pool_size,
            "available": available,
            "in_use": in_use,
            "get_count": self._pool_get_count,
            "return_count": self._pool_return_count,
            "timeout_count": self._pool_timeout_count,
            "high_watermark_in_use": self._pool_high_watermark_in_use,
        }

    def _init_database(self):
        """Initialize database schema and run migrations."""
        try:
            # Create schema if needed
            with self._get_connection() as conn:
                self._create_schema(conn)
                conn.commit()

            # Run migrations
            migrations = MigrationsHandler(self.db_path)
            migrations.run_migrations(self._get_connection)

            self.logger.info("Database initialization completed")
        except Exception as e:
            self.logger.exception("Failed to initialize database")
            raise DatabaseError(message="Failed to initialize database", cause=e)

    def _create_schema(self, conn):
        """Create core database schema tables."""
        # Users table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                username TEXT UNIQUE,
                password_hash TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Settings table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                user_id TEXT PRIMARY KEY,
                theme TEXT DEFAULT 'orange',
                dpi_scale INTEGER DEFAULT 100,
                autosave_interval INTEGER DEFAULT 30,
                notifications BOOLEAN DEFAULT 1,
                daily_reset_time TEXT DEFAULT '09:00',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """
        )

        # Tasks table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                project TEXT,
                owner TEXT,
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
                refreshed_at TEXT,
                recurrence_type TEXT,
                recurrence_param TEXT,
                snoozed_until TIMESTAMP,
                subtasks TEXT,
                parent_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """
        )

        # Notes table
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS notes (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT,
                folder_id TEXT,
                parent_id TEXT,
                pinned BOOLEAN DEFAULT 0,
                archived BOOLEAN DEFAULT 0,
                deleted BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        """
        )

    def _init_repositories(self):
        """Initialize repository classes."""
        # Create row converter dictionary for repositories that need it
        row_converters = {
            "_row_to_task_dict": self._row_to_task_dict,
            "_task_dict_to_row": self._task_dict_to_row,
        }
        
        self.task_repo = TaskRepository(self._get_connection, self._ensure_user_exists)
        self.archive_repo = ArchiveRepository(self._get_connection, self._ensure_user_exists, row_converters)
        self.user_repo = UserRepository(self._get_connection)
        self.strike_repo = StrikeRepository(self._get_connection, self._ensure_user_exists)
        self.analytics_repo = AnalyticsRepository(
            self._get_connection, self._ensure_user_exists, self._calculate_streak
        )
        self.note_repo = NoteRepository(self._get_connection, self._ensure_user_exists)
        self.logger.info("Repositories initialized")

    def _get_connection(self):
        """Get a database connection with proper configuration."""
        if not self.db_path or not isinstance(self.db_path, str):
            raise ValidationError(message="Invalid db_path")
        try:
            conn = sqlite3.connect(
                self.db_path, timeout=DB_CONNECTION_TIMEOUT, check_same_thread=False
            )
        except Exception as e:
            raise DatabaseError(
                message="Database unavailable",
                details={"db_path": self.db_path},
                cause=e,
            )
        try:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.row_factory = sqlite3.Row
            conn.execute("SELECT 1")
        except Exception as e:
            try:
                conn.close()
            except Exception:  # noqa: broad-except
                self.logger.exception("Failed to close unhealthy connection")
            raise DatabaseError(
                message="Database connection health check failed",
                details={"db_path": self.db_path},
                cause=e,
            )
        return conn

    def _ensure_user_exists(self, user_id: str) -> bool:
        """Ensure user exists in database, create if not."""
        try:
            return self.user_repo.ensure_user_exists(user_id)
        except Exception as e:
            self.logger.exception("Error ensuring user exists: %s", user_id)
            return False

    def _calculate_streak(self, user_id: str) -> int:
        """Calculate user's current streak."""
        try:
            return self.strike_repo.calculate_streak(user_id)
        except Exception as e:
            self.logger.exception("Error calculating streak for user %s", user_id)
            return 0

    def _task_dict_to_row(self, task: Dict[str, Any], user_id: str) -> tuple:
        """Convert task dict to database row tuple.
        
        Used by repositories for converting task dictionaries to database rows.
        Handles JSON serialization of complex fields like daily_strikes and subtasks.
        """
        import json
        return (
            task.get("id"),
            user_id,
            task.get("title", ""),
            task.get("description", ""),
            task.get("project", ""),
            task.get("owner", ""),
            task.get("priority", "medium"),
            task.get("status", "pending"),
            task.get("completed", False),
            task.get("completed_at"),
            task.get("due_date"),
            task.get("estimated_duration", 60),
            task.get("scheduled_hour"),
            task.get("scheduled_minute"),
            task.get("scheduled_date"),
            task.get("scheduled_duration"),
            task.get("struck_forever", False),
            task.get("struck_today", False),
            task.get("struck_date"),
            task.get("strike_report"),
            task.get("strike_count", 0),
            json.dumps(task.get("daily_strikes", {})),
            task.get("refreshed_at"),
            task.get("recurrence_type"),
            task.get("recurrence_param"),
            task.get("snoozed_until"),
            json.dumps(task.get("subtasks", [])),
            task.get("created_at"),
            task.get("updated_at"),
        )

    def _row_to_task_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert database row to task dict.
        
        Used by repositories for converting database rows back to task dictionaries.
        Handles JSON deserialization of complex fields.
        """
        import json
        return {
            "id": row["id"],
            "user_id": row["user_id"],
            "title": row["title"],
            "description": row["description"],
            "project": row["project"],
            "owner": row["owner"],
            "priority": row["priority"],
            "status": row["status"],
            "completed": bool(row["completed"]),
            "completed_at": row["completed_at"],
            "due_date": row["due_date"],
            "estimated_duration": row["estimated_duration"],
            "scheduled_hour": row["scheduled_hour"],
            "scheduled_minute": row["scheduled_minute"],
            "scheduled_date": row["scheduled_date"],
            "scheduled_duration": row["scheduled_duration"],
            "struck_forever": bool(row["struck_forever"]),
            "struck_today": bool(row["struck_today"]),
            "struck_date": row["struck_date"],
            "strike_report": row["strike_report"],
            "strike_count": row["strike_count"],
            "daily_strikes": json.loads(row["daily_strikes"] or "{}"),
            "refreshed_at": row["refreshed_at"],
            "recurrence_type": row["recurrence_type"],
            "recurrence_param": row["recurrence_param"],
            "snoozed_until": row["snoozed_until"],
            "subtasks": json.loads(row["subtasks"] or "[]"),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    # Public API methods delegating to repositories

    def load_tasks_for_user(self, user_id: str) -> Optional[List[Dict[str, Any]]]:
        """Load all tasks for a user."""
        return self.task_repo.load_tasks_for_user(user_id)

    def save_tasks_for_user(self, user_id: str, tasks: List[Dict[str, Any]]) -> bool:
        """Save tasks for a user."""
        return self.task_repo.save_tasks_for_user(user_id, tasks)

    def create_task_for_user(self, user_id: str, task_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Create a task for a user."""
        return self.task_repo.create_task_for_user(user_id, task_data)

    def update_task_for_user(
        self, user_id: str, task_id: str, task_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update a task for a user."""
        return self.task_repo.update_task_for_user(user_id, task_id, task_data)

    def get_task_for_user(self, user_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific task for a user."""
        return self.task_repo.get_task_for_user(user_id, task_id)

    def archive_task(self, user_id: str, task_id: str) -> bool:
        """Archive a task."""
        return self.archive_repo.archive_task(user_id, task_id)

    def delete_task(self, user_id: str, task_id: str) -> bool:
        """Delete a task."""
        return self.archive_repo.delete_task(user_id, task_id)

    def load_archived_tasks_for_user(self, user_id: str) -> Optional[List[Dict[str, Any]]]:
        """Load archived tasks for a user."""
        return self.archive_repo.load_archived_tasks_for_user(user_id)

    def restore_task(self, user_id: str, task_id: str) -> bool:
        """Restore an archived task."""
        return self.archive_repo.restore_task(user_id, task_id)

    def load_notes_for_user(self, user_id: str) -> Optional[List[Dict[str, Any]]]:
        """Load notes for a user."""
        return self.note_repo.load_notes_for_user(user_id)

    def create_note_for_user(
        self, user_id: str, note_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create a note for a user."""
        return self.note_repo.create_note_for_user(user_id, note_data)

    def update_note_for_user(
        self, user_id: str, note_id: str, note_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update a note for a user."""
        return self.note_repo.update_note_for_user(user_id, note_id, note_data)

    def delete_note_for_user(self, user_id: str, note_id: str) -> bool:
        """Delete a note for a user."""
        return self.note_repo.delete_note_for_user(user_id, note_id)

    def get_daily_recap(self, user_id: str, day: str) -> Optional[Dict[str, Any]]:
        """Get daily recap for a user."""
        return self.analytics_repo.get_daily_recap(user_id, day)

    def save_recap_feedback(
        self, user_id: str, recap_day: str, feedback: Dict[str, Any]
    ) -> bool:
        """Save feedback for a daily recap."""
        return self.analytics_repo.save_recap_feedback(user_id, recap_day, feedback)

    def load_recap_feedback(
        self, user_id: str, recap_day: str
    ) -> Optional[Dict[str, Any]]:
        """Load feedback for a daily recap."""
        return self.analytics_repo.load_recap_feedback(user_id, recap_day)

    def add_strike_event(
        self, user_id: str, task_id: str, day: str, strike_type: str
    ) -> bool:
        """Record a strike event."""
        return self.strike_repo.add_strike_event(user_id, task_id, day, strike_type)

    def load_strike_today_report_history(
        self, user_id: str, task_id: str, day: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Load strike report history."""
        return self.strike_repo.load_strike_today_report_history(user_id, task_id, day)

    def add_settings_change_event(self, user_id: str, day: str) -> bool:
        """Record a settings change event."""
        return self.strike_repo.add_settings_change_event(user_id, day)

    def record_user_heartbeat(self, user_id: str, day: str) -> bool:
        """Record user activity."""
        return self.strike_repo.record_user_heartbeat(user_id, day)

    def count_active_users(self, day: str) -> int:
        """Count active users on a given day."""
        return self.strike_repo.count_active_users(day)

    def get_user_settings(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user settings."""
        return self.user_repo.get_user_settings(user_id)

    def update_user_settings(self, user_id: str, settings: Dict[str, Any]) -> bool:
        """Update user settings."""
        return self.user_repo.update_user_settings(user_id, settings)

    def get_setting(self, user_id: str, setting_name: str) -> Any:
        """Get a specific user setting."""
        return self.user_repo.get_setting(user_id, setting_name)

    def set_setting(self, user_id: str, setting_name: str, value: Any) -> bool:
        """Set a specific user setting."""
        return self.user_repo.set_setting(user_id, setting_name, value)

    def save_deleted_task_snapshot(self, user_id: str, task: Dict[str, Any]) -> bool:
        """Save a snapshot of a deleted task."""
        return self.archive_repo.save_deleted_task_snapshot(user_id, task)

    def restore_deleted_task_snapshot(self, user_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        """Restore a deleted task from snapshot."""
        return self.archive_repo.restore_deleted_task_snapshot(user_id, task_id)
