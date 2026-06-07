import json
import logging
import os
import shutil
import sqlite3
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from queue import Empty, Full, Queue
from typing import Any, Dict, List, Optional

from src.constants import (
    BACKUP_RETENTION_DAYS,
    DB_CONNECTION_TIMEOUT,
    DB_POOL_WAIT_TIMEOUT,
    DEFAULT_USER_ID,
    MAX_BACKUP_SIZE_BYTES,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS,
)
from src.exceptions import (
    DatabaseError,
    DatabaseException,
    DataManagerException,
    TaskNotFoundException,
    ValidationError,
)


class SQLiteDataManager:
    """Thread-safe SQLite data manager with user-specific data isolation"""

    def __init__(self, data_dir="data", pool_size=5):
        # Handle PyInstaller bundle path
        if getattr(sys, "frozen", False):
            # Running as compiled executable
            base_path = os.path.dirname(sys.executable)
        else:
            # Running as script
            base_path = os.path.dirname(os.path.abspath(__file__))

        self.data_dir = os.path.join(base_path, data_dir)
        self.db_path = os.path.join(self.data_dir, "shakshuka.db")

        # Thread safety
        self._lock = threading.RLock()

        # Connection pool (Issue #23)
        self._pool_size = pool_size
        self._connection_pool = Queue(maxsize=pool_size)

        self._pool_get_count = 0
        self._pool_timeout_count = 0
        self._pool_return_count = 0
        self._pool_high_watermark_in_use = 0

        # Create data directory if it doesn't exist
        try:
            os.makedirs(self.data_dir, exist_ok=True)
            # Remove print, use logging (Issue #19)
        except Exception as e:
            raise DatabaseException(
                f"Failed to create data directory '{self.data_dir}': {e}"
            )

        # Setup logging
        self._setup_logging()
        self.logger.info("Data directory ensured: %s", os.path.abspath(self.data_dir))

        # Initialize connection pool
        self._init_connection_pool()

        # Initialize database
        self._init_database()

    def _setup_logging(self):
        """Setup logging for the data manager"""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def _init_connection_pool(self):
        """Initialize connection pool (Issue #23)"""
        try:
            for _ in range(self._pool_size):
                conn = sqlite3.connect(
                    self.db_path, timeout=DB_CONNECTION_TIMEOUT, check_same_thread=False
                )
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA journal_mode = WAL")
                conn.row_factory = sqlite3.Row
                self._connection_pool.put(conn)
            self.logger.info(
                "Connection pool initialized with %d connections", self._pool_size
            )
        except Exception as e:
            self.logger.exception("Failed to initialize connection pool")
            raise DatabaseException(f"Failed to initialize connection pool: {e}")

    def _get_pooled_connection(self):
        """Get connection from pool with timeout (Issue #23, #3)"""
        start = time.monotonic()
        in_use = None
        try:
            conn = self._connection_pool.get(timeout=DB_POOL_WAIT_TIMEOUT)
            self._pool_get_count += 1
            try:
                in_use = self._pool_size - self._connection_pool.qsize()
                if in_use > self._pool_high_watermark_in_use:
                    self._pool_high_watermark_in_use = in_use
            except Exception:  # noqa: broad-except - Data layer defensive exception handling
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
            except Exception:  # noqa: broad-except - Data layer defensive exception handling
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
        """Return connection to pool (Issue #3)"""
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
            except Exception:  # noqa: broad-except - Data layer defensive exception handling
                self.logger.exception("Failed to close connection after pool full")
        except Exception:  # noqa: broad-except - Data layer defensive exception handling
            self.logger.exception("Failed to return connection to pool")
            try:
                conn.close()
            except Exception:  # noqa: broad-except - Data layer defensive exception handling
                self.logger.exception("Failed to close connection after return failure")

    @contextmanager
    def pooled_connection(self):
        conn = self._get_pooled_connection()
        try:
            yield conn
        finally:
            try:
                conn.rollback()
            except Exception:  # noqa: broad-except - Data layer defensive exception handling
                self.logger.exception("Failed to rollback pooled DB connection")
            try:
                self._return_connection(conn)
            except Exception:  # noqa: broad-except - Data layer defensive exception handling
                self.logger.exception("Failed to return pooled DB connection")

    def get_pool_stats(self) -> Dict[str, Any]:
        try:
            available = self._connection_pool.qsize()
        except Exception:  # noqa: broad-except - Data layer defensive exception handling
            available = None
        in_use = None
        try:
            if isinstance(available, int):
                in_use = self._pool_size - available
        except Exception:  # noqa: broad-except - Data layer defensive exception handling
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
        """Initialize SQLite database with required tables"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("PRAGMA foreign_keys = ON")
                conn.execute("PRAGMA journal_mode = WAL")

                # Create users table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        username TEXT UNIQUE,
                        password_hash TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Create tasks table
                conn.execute("""
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
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                """)

                # Create notes table (simple text notes per user)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS notes (
                        id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        title TEXT NOT NULL,
                        content TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                """)

                # Create settings table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS settings (
                        user_id TEXT PRIMARY KEY,
                        theme TEXT DEFAULT 'orange',
                        dpi_scale INTEGER DEFAULT 100,
                        autosave_interval INTEGER DEFAULT 30,
                        notifications BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                """)

                # Create sessions table
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        session_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                """)

                # Create user_heartbeat table for tracking active users
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS user_heartbeat (
                        user_id TEXT PRIMARY KEY,
                        last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                """)

                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS deleted_tasks (
                        user_id TEXT NOT NULL,
                        task_id TEXT NOT NULL,
                        task_json TEXT NOT NULL,
                        deleted_at TEXT NOT NULL,
                        PRIMARY KEY (user_id, task_id)
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_deleted_tasks_user_id ON deleted_tasks (user_id)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_deleted_tasks_deleted_at ON deleted_tasks (deleted_at)"
                )

                # Create indexes for better performance
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tasks_user_id ON tasks (user_id)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks (completed)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_notes_user_id ON notes (user_id, updated_at DESC)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions (user_id)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions (expires_at)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_user_heartbeat_last_seen ON user_heartbeat (last_seen_at)"
                )

                conn.commit()
                self.logger.info(f"Database initialized successfully: {self.db_path}")

                # Run database migrations (must run before creating indexes that depend on migrated columns)
                self._run_migrations()

                # Ensure columns exist even if migration version bookkeeping is stale
                try:
                    cursor = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'"
                    )
                    if cursor.fetchone():
                        col_cursor = conn.execute("PRAGMA table_info(user_preferences)")
                        columns = [row[1] for row in col_cursor.fetchall()]
                        if "last_daily_reset_at" not in columns:
                            conn.execute(
                                "ALTER TABLE user_preferences ADD COLUMN last_daily_reset_at TEXT"
                            )

                    cursor = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='settings'"
                    )
                    if cursor.fetchone():
                        col_cursor = conn.execute("PRAGMA table_info(settings)")
                        columns = [row[1] for row in col_cursor.fetchall()]
                        if "last_daily_reset_at" not in columns:
                            conn.execute(
                                "ALTER TABLE settings ADD COLUMN last_daily_reset_at TEXT"
                            )

                    conn.commit()
                except Exception as e:
                    self.logger.warning(
                        f"Could not ensure last_daily_reset_at columns during init: {e}"
                    )

                # Create indexes that depend on migrated columns (after migrations)
                try:
                    with self._get_connection() as conn:
                        # Check if scheduled_date column exists before creating index
                        cursor = conn.execute("PRAGMA table_info(tasks)")
                        columns = [row[1] for row in cursor.fetchall()]
                        if "scheduled_date" in columns:
                            conn.execute(
                                "CREATE INDEX IF NOT EXISTS idx_tasks_user_scheduled ON tasks (user_id, scheduled_date)"
                            )
                            conn.commit()
                except Exception as e:
                    self.logger.warning(
                        f"Could not create scheduled_date index (column may not exist yet): {e}"
                    )

        except Exception as e:
            self.logger.error(f"Error initializing database: {e}")
            raise

    def _migration_013_last_daily_reset_at(self, conn) -> List[Dict[str, Any]]:
        migrations_applied = []
        try:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'"
            )
            if cursor.fetchone():
                col_cursor = conn.execute("PRAGMA table_info(user_preferences)")
                columns = [row[1] for row in col_cursor.fetchall()]
                if "last_daily_reset_at" not in columns:
                    conn.execute(
                        "ALTER TABLE user_preferences ADD COLUMN last_daily_reset_at TEXT"
                    )
                    self.logger.info(
                        "Added last_daily_reset_at column to user_preferences table"
                    )

            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='settings'"
            )
            if cursor.fetchone():
                col_cursor = conn.execute("PRAGMA table_info(settings)")
                columns = [row[1] for row in col_cursor.fetchall()]
                if "last_daily_reset_at" not in columns:
                    conn.execute(
                        "ALTER TABLE settings ADD COLUMN last_daily_reset_at TEXT"
                    )
                    self.logger.info(
                        "Added last_daily_reset_at column to settings table"
                    )

            migrations_applied.append(
                {
                    "version": 13,
                    "description": "Added last_daily_reset_at column to settings tables",
                    "sql": "ALTER TABLE user_preferences/settings ADD COLUMN last_daily_reset_at TEXT",
                }
            )
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 013 failed: {e}")
            raise

    def _migration_014_mobile_inbox(self, conn) -> List[Dict[str, Any]]:
        migrations_applied: List[Dict[str, Any]] = []
        try:
            conn.execute(
                """
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
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mobile_devices_user_token ON mobile_devices (user_id, token_hash)"
            )

            conn.execute(
                """
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
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mobile_inbox_user_status_created ON mobile_inbox (user_id, status, created_at)"
            )

            migrations_applied.append(
                {
                    "version": 14,
                    "description": "Created mobile_devices and mobile_inbox tables",
                    "sql": "CREATE TABLE mobile_devices/mobile_inbox",
                }
            )

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 014 failed: {e}")
            raise

    def _migration_015_settings_events(self, conn) -> List[Dict[str, Any]]:
        """Migration 15: Create settings_events table for tracking settings changes."""
        migrations_applied: List[Dict[str, Any]] = []
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    setting_key TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_settings_events_user_timestamp ON settings_events (user_id, timestamp)"
            )

            migrations_applied.append(
                {
                    "version": 15,
                    "description": "Created settings_events table for streak activity tracking",
                    "sql": "CREATE TABLE settings_events",
                }
            )

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 015 failed: {e}")
            raise

    def _migration_016_deleted_tasks(self, conn) -> List[Dict[str, Any]]:
        migrations_applied: List[Dict[str, Any]] = []
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS deleted_tasks (
                    user_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    task_json TEXT NOT NULL,
                    deleted_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, task_id)
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_deleted_tasks_user_id ON deleted_tasks (user_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_deleted_tasks_deleted_at ON deleted_tasks (deleted_at)"
            )

            migrations_applied.append(
                {
                    "version": 16,
                    "description": "Created deleted_tasks table",
                    "sql": "CREATE TABLE deleted_tasks",
                }
            )
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 016 failed: {e}")
            raise

    def _migration_017_daily_reset_count(self, conn) -> List[Dict[str, Any]]:
        """Migration 17: Add daily_reset_count to settings table for analytics."""
        migrations_applied: List[Dict[str, Any]] = []
        try:
            # Check if column already exists
            cursor = conn.execute("PRAGMA table_info(settings)")
            columns = [row[1] for row in cursor.fetchall()]

            if "daily_reset_count" not in columns:
                conn.execute(
                    "ALTER TABLE settings ADD COLUMN daily_reset_count INTEGER DEFAULT 0"
                )
                self.logger.info("Added daily_reset_count column to settings table")

            migrations_applied.append(
                {
                    "version": 17,
                    "description": "Added daily_reset_count to settings for analytics",
                    "sql": "ALTER TABLE settings ADD COLUMN daily_reset_count INTEGER DEFAULT 0",
                }
            )
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 017 failed: {e}")
            raise

    def _migration_018_notes_folders(self, conn) -> List[Dict[str, Any]]:
        """Migration 18: Add folder support to notes table for explorer-style UI."""
        migrations_applied: List[Dict[str, Any]] = []
        try:
            cursor = conn.execute("PRAGMA table_info(notes)")
            columns = [row[1] for row in cursor.fetchall()]

            if "folder" not in columns:
                conn.execute("ALTER TABLE notes ADD COLUMN folder TEXT")
                self.logger.info("Added folder column to notes table")
                migrations_applied.append(
                    {
                        "version": 18,
                        "description": "Added folder column to notes table",
                        "sql": "ALTER TABLE notes ADD COLUMN folder TEXT",
                    }
                )

            # Index to speed up folder-based queries in the upcoming notes dashboard
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_notes_user_folder ON notes (user_id, folder, updated_at)"
            )
            migrations_applied.append(
                {
                    "version": 18,
                    "description": "Created idx_notes_user_folder index",
                    "sql": "CREATE INDEX IF NOT EXISTS idx_notes_user_folder ON notes (user_id, folder, updated_at)",
                }
            )

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 018 failed: {e}")
            raise

    def _migration_019_daily_reset_log(self, conn) -> List[Dict[str, Any]]:
        """Migration 19: Create daily_reset_log table for daily reset summaries."""
        migrations_applied: List[Dict[str, Any]] = []
        try:
            # Create table if it does not exist. This is idempotent and safe on
            # existing installs.
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_reset_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    reset_at TEXT NOT NULL,
                    task_count INTEGER NOT NULL,
                    tasks_json TEXT NOT NULL,
                    seen INTEGER NOT NULL DEFAULT 0,
                    reset_reason TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_daily_reset_log_user_seen_reset "
                "ON daily_reset_log (user_id, seen, reset_at DESC)"
            )

            migrations_applied.append(
                {
                    "version": 19,
                    "description": "Created daily_reset_log table and user_seen_reset index",
                    "sql": "CREATE TABLE IF NOT EXISTS daily_reset_log (...)",
                }
            )

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 019 failed: {e}")
            raise

    def _migration_020_tasks_recurrence_snooze(self, conn) -> List[Dict[str, Any]]:
        """Migration 20: Add recurrence/snooze fields to tasks table.

        Columns (all nullable, backward compatible):
        - recurrence_type TEXT
        - recurrence_param INTEGER
        - snoozed_until TEXT (YYYY-MM-DD)
        """
        migrations_applied: List[Dict[str, Any]] = []
        try:
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]

            if "recurrence_type" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN recurrence_type TEXT")
            if "recurrence_param" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN recurrence_param INTEGER")
            if "snoozed_until" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN snoozed_until TEXT")

            migrations_applied.append(
                {
                    "version": 20,
                    "description": "Added recurrence_type, recurrence_param, snoozed_until columns to tasks",
                    "sql": "ALTER TABLE tasks ADD COLUMN recurrence_type/recurrence_param/snoozed_until",
                }
            )
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 020 failed: {e}")
            raise

    def _migration_021_notes_pin_archive(self, conn) -> List[Dict[str, Any]]:
        """Migration 21: Add pinned/archived flags to notes table."""
        migrations_applied: List[Dict[str, Any]] = []
        try:
            cursor = conn.execute("PRAGMA table_info(notes)")
            columns = [row[1] for row in cursor.fetchall()]

            if "pinned" not in columns:
                conn.execute("ALTER TABLE notes ADD COLUMN pinned INTEGER DEFAULT 0")
            if "archived" not in columns:
                conn.execute("ALTER TABLE notes ADD COLUMN archived INTEGER DEFAULT 0")

            migrations_applied.append(
                {
                    "version": 21,
                    "description": "Added pinned/archived columns to notes",
                    "sql": "ALTER TABLE notes ADD COLUMN pinned/archived",
                }
            )
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 021 failed: {e}")
            raise

    def _migration_022_daily_recap_feedback(self, conn) -> List[Dict[str, Any]]:
        """Migration 22: Create daily_recap_feedback table for recap questions."""
        migrations_applied: List[Dict[str, Any]] = []
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_recap_feedback (
                    user_id TEXT NOT NULL,
                    recap_day TEXT NOT NULL,
                    question_key TEXT NOT NULL,
                    answer TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, recap_day, question_key),
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_daily_recap_feedback_user_day "
                "ON daily_recap_feedback (user_id, recap_day)"
            )
            migrations_applied.append(
                {
                    "version": 22,
                    "description": "Created daily_recap_feedback table",
                    "sql": "CREATE TABLE daily_recap_feedback",
                }
            )
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 022 failed: {e}")
            raise

    def _migration_023_compact_mode_setting(self, conn) -> List[Dict[str, Any]]:
        """Migration 23: Add compact_mode flag to user_preferences/settings.

        This is defensive; save_settings_for_user also ensures the column exists
        at runtime, but having a migration keeps the schema consistent.
        """
        migrations_applied: List[Dict[str, Any]] = []
        try:
            cursor = conn.execute("PRAGMA table_info(user_preferences)")
            columns = [row[1] for row in cursor.fetchall()]
            if "compact_mode" not in columns:
                conn.execute(
                    "ALTER TABLE user_preferences ADD COLUMN compact_mode INTEGER DEFAULT 0"
                )

            cursor = conn.execute("PRAGMA table_info(settings)")
            columns = [row[1] for row in cursor.fetchall()]
            if "compact_mode" not in columns:
                conn.execute(
                    "ALTER TABLE settings ADD COLUMN compact_mode INTEGER DEFAULT 0"
                )

            migrations_applied.append(
                {
                    "version": 23,
                    "description": "Added compact_mode column to user_preferences/settings",
                    "sql": "ALTER TABLE user_preferences/settings ADD COLUMN compact_mode",
                }
            )
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 023 failed: {e}")
            raise

    def _migration_024_notes_trash_versions_subtasks(
        self, conn
    ) -> List[Dict[str, Any]]:
        """Migration 24: Notes trash (deleted_at), note version history, task subtasks.

        Schema additions:
        - notes.deleted_at TEXT  (soft-delete timestamp, NULL = not deleted)
        - note_versions table   (snapshot previous content on each update)
        - tasks.subtasks TEXT    (JSON array of sub-task objects)
        """
        migrations_applied: List[Dict[str, Any]] = []
        try:
            # 1) notes.deleted_at for soft-delete / trash
            cursor = conn.execute("PRAGMA table_info(notes)")
            notes_cols = [row[1] for row in cursor.fetchall()]
            if "deleted_at" not in notes_cols:
                conn.execute("ALTER TABLE notes ADD COLUMN deleted_at TEXT")
                self.logger.info("Added deleted_at column to notes table")

            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_notes_user_deleted "
                "ON notes (user_id, deleted_at)"
            )

            # 2) note_versions table
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS note_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    title TEXT,
                    content TEXT,
                    saved_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_note_versions_note_saved "
                "ON note_versions (note_id, saved_at DESC)"
            )

            # 3) tasks.subtasks JSON column
            cursor = conn.execute("PRAGMA table_info(tasks)")
            tasks_cols = [row[1] for row in cursor.fetchall()]
            if "subtasks" not in tasks_cols:
                conn.execute("ALTER TABLE tasks ADD COLUMN subtasks TEXT")
                self.logger.info("Added subtasks column to tasks table")

            migrations_applied.append(
                {
                    "version": 24,
                    "description": "Added notes.deleted_at, note_versions table, tasks.subtasks column",
                    "sql": "Migration 024: notes trash + versions + subtasks",
                }
            )
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 024 failed: {e}")
            raise

    def _migration_025_owner_column(self, conn) -> List[Dict[str, Any]]:
        """Migration 025: Add owner column to tasks table"""
        migrations_applied = []
        try:
            cursor = conn.execute("PRAGMA table_info(tasks)")
            tasks_cols = [row[1] for row in cursor.fetchall()]
            if "owner" not in tasks_cols:
                conn.execute("ALTER TABLE tasks ADD COLUMN owner TEXT DEFAULT ''")
                self.logger.info("Added owner column to tasks table")

            migrations_applied.append(
                {
                    "version": 25,
                    "description": "Added owner column to tasks table",
                    "sql": "Migration 025: tasks.owner",
                }
            )
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 025 failed: {e}")
            raise

    def _migration_026_mobile_sync_requests(self, conn) -> List[Dict[str, Any]]:
        """Migration 026: Create mobile_sync_requests table for persistent sync state"""
        migrations_applied: List[Dict[str, Any]] = []
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mobile_sync_requests (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    consumed_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mobile_sync_requests_user_expires ON mobile_sync_requests (user_id, expires_at)"
            )

            # Add sequence_num to mobile_inbox for deterministic ordering
            cursor = conn.execute("PRAGMA table_info(mobile_inbox)")
            inbox_cols = [row[1] for row in cursor.fetchall()]
            if "sequence_num" not in inbox_cols:
                conn.execute(
                    "ALTER TABLE mobile_inbox ADD COLUMN sequence_num INTEGER DEFAULT 0"
                )
                self.logger.info("Added sequence_num column to mobile_inbox table")

            migrations_applied.append(
                {
                    "version": 26,
                    "description": "Created mobile_sync_requests table and added sequence_num to mobile_inbox",
                    "sql": "CREATE TABLE mobile_sync_requests",
                }
            )

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 026 failed: {e}")
            raise

    def _run_migrations(self):
        """Run database migrations with comprehensive error handling and rollback"""
        migration_version = None
        backup_created = False

        try:
            with self._get_connection() as conn:
                # Start transaction for migration
                conn.execute("BEGIN IMMEDIATE TRANSACTION")

                try:
                    # Get current migration version
                    migration_version = self._get_migration_version(conn)
                    self.logger.info(f"Current migration version: {migration_version}")

                    # Create backup before major migrations
                    if migration_version < 2:
                        backup_created = self._create_migration_backup(conn)
                        if backup_created:
                            self.logger.info("Migration backup created successfully")

                    # Run migrations based on version
                    migrations_applied = []

                    # Migration 1: Add analytics columns
                    if migration_version < 1:
                        migrations_applied.extend(
                            self._migration_001_analytics_columns(conn)
                        )

                    # Migration 2: Add indexes and constraints
                    if migration_version < 2:
                        migrations_applied.extend(
                            self._migration_002_indexes_constraints(conn)
                        )

                    # Migration 3: Add user preferences
                    if migration_version < 3:
                        migrations_applied.extend(
                            self._migration_003_user_preferences(conn)
                        )

                    # Migration 4: Add audit trail
                    if migration_version < 4:
                        migrations_applied.extend(self._migration_004_audit_trail(conn))

                    # Migration 5: Add planner v2 tables
                    if migration_version < 5:
                        migrations_applied.extend(self._migration_005_planner_v2(conn))

                    # Migration 6: Add scheduled_date and scheduled_minute fields
                    if migration_version < 6:
                        migrations_applied.extend(
                            self._migration_006_scheduled_fields(conn)
                        )

                    # Migration 7: Add daily_strikes column to persist per-day strike counts
                    if migration_version < 7:
                        migrations_applied.extend(
                            self._migration_007_daily_strikes(conn)
                        )

                    # Migration 8: Add planner daily history snapshots
                    if migration_version < 8:
                        migrations_applied.extend(
                            self._migration_008_planner_history(conn)
                        )

                    # Migration 9: Add strike-today report history events
                    if migration_version < 9:
                        migrations_applied.extend(
                            self._migration_009_strike_report_history(conn)
                        )

                    # Migration 10: Add struck_forever column to tasks table
                    if migration_version < 10:
                        migrations_applied.extend(
                            self._migration_010_struck_forever(conn)
                        )

                    # Migration 11: Add analytics history tables for strike calendar and daily recap
                    if migration_version < 11:
                        migrations_applied.extend(
                            self._migration_011_analytics_history(conn)
                        )

                    # Migration 12: Add refreshed_at column for daily reset badge
                    if migration_version < 12:
                        migrations_applied.extend(
                            self._migration_012_refreshed_at(conn)
                        )

                    # Migration 13: Add last_daily_reset_at to user_preferences/settings for robust missed reset detection
                    if migration_version < 13:
                        migrations_applied.extend(
                            self._migration_013_last_daily_reset_at(conn)
                        )

                    if migration_version < 14:
                        migrations_applied.extend(
                            self._migration_014_mobile_inbox(conn)
                        )

                    # Migration 15: Add settings_events table for streak tracking
                    if migration_version < 15:
                        migrations_applied.extend(
                            self._migration_015_settings_events(conn)
                        )

                    if migration_version < 16:
                        migrations_applied.extend(
                            self._migration_016_deleted_tasks(conn)
                        )

                    if migration_version < 17:
                        migrations_applied.extend(
                            self._migration_017_daily_reset_count(conn)
                        )

                    # Migration 18: Add folder support for notes (explorer-style dashboard)
                    if migration_version < 18:
                        migrations_applied.extend(
                            self._migration_018_notes_folders(conn)
                        )

                    # Migration 19: Create daily_reset_log table for daily reset summaries
                    if migration_version < 19:
                        migrations_applied.extend(
                            self._migration_019_daily_reset_log(conn)
                        )

                    # Migration 20: Add recurrence/snooze fields to tasks
                    if migration_version < 20:
                        migrations_applied.extend(
                            self._migration_020_tasks_recurrence_snooze(conn)
                        )

                    # Migration 21: Add pinned/archived flags to notes
                    if migration_version < 21:
                        migrations_applied.extend(
                            self._migration_021_notes_pin_archive(conn)
                        )

                    # Migration 22: Add daily_recap_feedback table
                    if migration_version < 22:
                        migrations_applied.extend(
                            self._migration_022_daily_recap_feedback(conn)
                        )

                    # Migration 23: Add compact_mode setting
                    if migration_version < 23:
                        migrations_applied.extend(
                            self._migration_023_compact_mode_setting(conn)
                        )

                    # Migration 24: Notes trash, version history, task subtasks
                    if migration_version < 24:
                        migrations_applied.extend(
                            self._migration_024_notes_trash_versions_subtasks(conn)
                        )

                    # Migration 25: Add owner column to tasks
                    if migration_version < 25:
                        migrations_applied.extend(
                            self._migration_025_owner_column(conn)
                        )

                    # Migration 26: Add mobile_sync_requests table and sequence_num to mobile_inbox
                    if migration_version < 26:
                        migrations_applied.extend(
                            self._migration_026_mobile_sync_requests(conn)
                        )

                    # Migration 27: Add missing indexes for common queries
                    if migration_version < 27:
                        migrations_applied.extend(
                            self._migration_027_add_missing_indexes(conn)
                        )

                    # Migration 28: Add parent_id for task nesting
                    if migration_version < 28:
                        migrations_applied.extend(
                            self._migration_028_task_nesting_parent_id(conn)
                        )

                    # Migration 29: Add parent_id for notes nesting
                    if migration_version < 29:
                        migrations_applied.extend(
                            self._migration_029_notes_nesting_parent_id(conn)
                        )

                    # Migration 30: Create archived_tasks table for task archival system
                    if migration_version < 30:
                        migrations_applied.extend(
                            self._migration_030_archived_tasks_table(conn)
                        )

                    # Update migration version
                    if migrations_applied:
                        new_version = max([m["version"] for m in migrations_applied])
                        self._update_migration_version(conn, new_version)
                        self.logger.info(f"Updated migration version to {new_version}")

                    # Commit transaction
                    conn.commit()
                    self.logger.info(
                        f"Database migrations completed successfully: {len(migrations_applied)} migrations applied"
                    )

                except Exception as inner_e:
                    # Rollback transaction on any error
                    try:
                        conn.rollback()
                    except Exception:  # noqa: broad-except - Data layer defensive exception handling
                        self.logger.exception("Migration rollback failed")
                    self.logger.exception("Migration transaction failed")

                    # Restore backup if created
                    if backup_created:
                        try:
                            self._restore_migration_backup()
                            self.logger.info("Migration backup restored successfully")
                        except Exception as restore_e:
                            self.logger.error(
                                f"Failed to restore migration backup: {restore_e}"
                            )

                    raise inner_e

        except Exception as e:
            self.logger.exception(
                "Error running database migrations (migration_version=%s, backup_created=%s)",
                migration_version,
                backup_created,
            )
            raise DatabaseError(
                message="Database migrations failed",
                details={
                    "migration_version": migration_version,
                    "backup_created": backup_created,
                },
                cause=e,
            )

    def save_deleted_task_snapshot(self, user_id: str, task: Dict[str, Any]) -> bool:
        try:
            self._ensure_user_exists(user_id)
            task_id = str(task.get("id") or "").strip()
            if not task_id:
                return False

            payload = json.dumps(task)
            now = datetime.now().isoformat()

            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                conn.execute(
                    "INSERT OR REPLACE INTO deleted_tasks (user_id, task_id, task_json, deleted_at) VALUES (?, ?, ?, ?)",
                    (user_id, task_id, payload, now),
                )
                conn.commit()
            return True
        except Exception as e:
            self.logger.error(
                f"Error saving deleted task snapshot for user {user_id}: {e}"
            )
            return False

    def _sanitize_text(self, value: Any, max_len: int) -> str:
        if value is None:
            return ""
        if not isinstance(value, str):
            value = str(value)
        value = value.strip()
        if len(value) > max_len:
            value = value[:max_len]
        return value

    def _normalize_task_dict(self, task: Dict[str, Any]) -> Dict[str, Any]:
        if task is None or not isinstance(task, dict):
            return {}

        normalized = dict(task)

        normalized["id"] = self._sanitize_text(normalized.get("id"), 64)
        normalized["title"] = self._sanitize_text(normalized.get("title"), 200)
        normalized["description"] = self._sanitize_text(
            normalized.get("description", ""), 10000
        )
        normalized["project"] = self._sanitize_text(normalized.get("project", ""), 200)
        normalized["owner"] = self._sanitize_text(normalized.get("owner", ""), 200)
        normalized["priority"] = (
            self._sanitize_text(normalized.get("priority", "medium"), 32) or "medium"
        )
        normalized["status"] = (
            self._sanitize_text(normalized.get("status", "pending"), 32) or "pending"
        )

        if "completed" in normalized:
            normalized["completed"] = bool(normalized.get("completed"))
        else:
            normalized["completed"] = False

        if "struck_forever" in normalized:
            normalized["struck_forever"] = bool(normalized.get("struck_forever"))
        else:
            normalized["struck_forever"] = False

        if "struck_today" in normalized:
            normalized["struck_today"] = bool(normalized.get("struck_today"))
        else:
            normalized["struck_today"] = False

        try:
            normalized["strike_count"] = int(normalized.get("strike_count", 0) or 0)
        except Exception:  # noqa: broad-except - Data layer defensive exception handling
            normalized["strike_count"] = 0

        try:
            normalized["estimated_duration"] = int(
                normalized.get("estimated_duration", 60) or 60
            )
        except Exception:  # noqa: broad-except - Data layer defensive exception handling
            normalized["estimated_duration"] = 60

        daily_strikes = normalized.get("daily_strikes", {})
        if not isinstance(daily_strikes, dict):
            daily_strikes = {}
        normalized["daily_strikes"] = daily_strikes

        # Recurrence fields (optional):
        # - recurrence_type: '', 'daily', 'weekly', 'every_n_days'
        # - recurrence_param: integer parameter (e.g. weekday index or N days)
        # - snoozed_until: YYYY-MM-DD date string used for "hide until" / snooze
        raw_recur_type = normalized.get("recurrence_type", "")
        if isinstance(raw_recur_type, str):
            recur_type = self._sanitize_text(raw_recur_type.lower(), 32)
        else:
            recur_type = ""
        if recur_type not in ("", "daily", "weekly", "every_n_days"):
            recur_type = ""
        normalized["recurrence_type"] = recur_type

        raw_param = normalized.get("recurrence_param")
        if raw_param is None or raw_param == "":
            normalized["recurrence_param"] = None
        else:
            try:
                normalized["recurrence_param"] = int(raw_param)
            except Exception:  # noqa: broad-except - Data layer defensive exception handling
                normalized["recurrence_param"] = None

        raw_snoozed = normalized.get("snoozed_until")
        if isinstance(raw_snoozed, str):
            # Store a simple YYYY-MM-DD string; scheduler/routes enforce semantics.
            normalized["snoozed_until"] = raw_snoozed.strip() or None
        else:
            normalized["snoozed_until"] = None

        # Subtasks: JSON array of sub-task objects
        raw_subtasks = normalized.get("subtasks")
        if isinstance(raw_subtasks, list):
            normalized["subtasks"] = raw_subtasks
        elif isinstance(raw_subtasks, str):
            try:
                parsed = json.loads(raw_subtasks)
                normalized["subtasks"] = parsed if isinstance(parsed, list) else []
            except Exception:  # noqa: broad-except
                normalized["subtasks"] = []
        else:
            normalized["subtasks"] = normalized.get("subtasks") or []

        now_iso = datetime.now().isoformat()
        normalized["created_at"] = normalized.get("created_at") or now_iso
        normalized["updated_at"] = normalized.get("updated_at") or now_iso

        if "strike_report" in normalized:
            normalized["strike_report"] = self._sanitize_text(
                normalized.get("strike_report"), 5000
            )

        return normalized

    def restore_deleted_task_snapshot(
        self, user_id: str, task_id: str
    ) -> Optional[Dict[str, Any]]:
        try:
            self._ensure_user_exists(user_id)
            task_id = str(task_id or "").strip()
            if not task_id:
                return None

            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                cur = conn.execute(
                    "SELECT task_json FROM deleted_tasks WHERE user_id = ? AND task_id = ?",
                    (user_id, task_id),
                )
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    return None

                exists_cur = conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE user_id = ? AND id = ?",
                    (user_id, task_id),
                )
                if exists_cur.fetchone()[0] != 0:
                    conn.rollback()
                    return None

                try:
                    task = json.loads(row["task_json"]) if row["task_json"] else None
                except Exception:  # noqa: broad-except - Data layer defensive exception handling
                    task = None

                if not isinstance(task, dict) or not str(task.get("id") or "").strip():
                    conn.rollback()
                    return None

                task_row = self._task_dict_to_row(task, user_id)
                conn.execute(
                    """
                    INSERT INTO tasks (
                        id, user_id, title, description, project, owner, priority, status,
                        completed, completed_at, due_date, estimated_duration, scheduled_hour,
                        scheduled_minute, scheduled_date, scheduled_duration, struck_forever, struck_today, struck_date, strike_report, strike_count,
                        daily_strikes, refreshed_at, recurrence_type, recurrence_param, snoozed_until, subtasks, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    task_row,
                )
                conn.execute(
                    "DELETE FROM deleted_tasks WHERE user_id = ? AND task_id = ?",
                    (user_id, task_id),
                )
                conn.commit()

            return task
        except Exception as e:
            self.logger.exception(
                "Error restoring deleted task snapshot for user %s, task %s",
                user_id,
                task_id,
            )
            raise DatabaseError(
                message="Error restoring deleted task snapshot",
                details={"user_id": user_id, "task_id": task_id},
                cause=e,
            )

    def _get_migration_version(self, conn) -> int:
        """Get current migration version from database"""
        try:
            cursor = conn.execute(
                "SELECT version FROM migration_version ORDER BY version DESC LIMIT 1"
            )
            result = cursor.fetchone()
            return result[0] if result else 0
        except sqlite3.OperationalError:
            # Migration version table doesn't exist, create it
            self.logger.info("migration_version table missing; creating")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS migration_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
            """)
            conn.execute(
                'INSERT INTO migration_version (version, description) VALUES (0, "Initial version")'
            )
            return 0

    def _update_migration_version(self, conn, version: int):
        """Update migration version in database"""
        conn.execute(
            "INSERT OR REPLACE INTO migration_version (version, description) VALUES (?, ?)",
            (version, f"Migration {version} applied"),
        )

    def _create_migration_backup(self, conn) -> bool:
        """Create backup before major migrations (Issue #9)"""
        try:
            backup_path = f"{self.db_path}.migration_backup_{int(time.time())}"

            # Create backup by copying database file
            shutil.copy2(self.db_path, backup_path)

            # Store backup path for potential restoration
            conn.execute("""
                CREATE TABLE IF NOT EXISTS migration_backups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backup_path TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    migration_version INTEGER
                )
            """)

            current_version = self._get_migration_version(conn)
            conn.execute(
                "INSERT INTO migration_backups (backup_path, migration_version) VALUES (?, ?)",
                (backup_path, current_version),
            )

            # Clean up old backups (Issue #9)
            self._cleanup_old_backups(conn)

            return True
        except Exception as e:
            self.logger.error("Failed to create migration backup: %s", e)
            return False

    def _cleanup_old_backups(self, conn):
        """Clean up old migration backups (Issue #9)
        - Keep backups from last 7 days
        - Clean backups older than 7 days
        - If total size exceeds 512MB, keep only latest backup
        """
        try:
            # Get all backups
            cursor = conn.execute("""
                SELECT id, backup_path, created_at
                FROM migration_backups
                ORDER BY created_at DESC
            """)
            backups = cursor.fetchall()

            if not backups:
                return

            # Calculate total backup size
            total_size = 0
            backup_info = []
            for backup in backups:
                backup_id, backup_path, created_at = backup
                if os.path.exists(backup_path):
                    size = os.path.getsize(backup_path)
                    total_size += size
                    backup_info.append(
                        {
                            "id": backup_id,
                            "path": backup_path,
                            "created_at": created_at,
                            "size": size,
                        }
                    )
                else:
                    # Remove reference to non-existent backup
                    conn.execute(
                        "DELETE FROM migration_backups WHERE id = ?", (backup_id,)
                    )

            # If total size exceeds limit, keep only latest backup
            if total_size > MAX_BACKUP_SIZE_BYTES:
                self.logger.warning(
                    "Backup size (%d MB) exceeds limit (%d MB), keeping only latest backup",
                    total_size // (1024 * 1024),
                    MAX_BACKUP_SIZE_BYTES // (1024 * 1024),
                )
                for i, backup in enumerate(backup_info):
                    if i > 0:  # Keep first (latest) backup only
                        try:
                            os.remove(backup["path"])
                            conn.execute(
                                "DELETE FROM migration_backups WHERE id = ?",
                                (backup["id"],),
                            )
                            self.logger.info(
                                "Removed backup due to size limit: %s", backup["path"]
                            )
                        except Exception as e:
                            self.logger.error(
                                "Failed to remove backup %s: %s", backup["path"], e
                            )
                return

            # Clean up backups older than BACKUP_RETENTION_DAYS
            cutoff_date = datetime.now() - timedelta(days=BACKUP_RETENTION_DAYS)

            for backup in backup_info:
                try:
                    # Parse created_at timestamp
                    created_dt = datetime.fromisoformat(
                        backup["created_at"].replace("Z", "+00:00")
                    )

                    # Compare in local time to match app behavior and avoid mixing aware/naive datetimes.
                    try:
                        if created_dt.tzinfo is not None:
                            created_dt_local = created_dt.astimezone().replace(
                                tzinfo=None
                            )
                        else:
                            created_dt_local = created_dt
                    except Exception:  # noqa: broad-except - Data layer defensive exception handling
                        created_dt_local = created_dt.replace(tzinfo=None)

                    if created_dt_local < cutoff_date:
                        os.remove(backup["path"])
                        conn.execute(
                            "DELETE FROM migration_backups WHERE id = ?",
                            (backup["id"],),
                        )
                        self.logger.info("Removed old backup: %s", backup["path"])
                except Exception as e:
                    self.logger.error(
                        "Failed to process backup %s: %s", backup["path"], e
                    )

            conn.commit()

        except Exception as e:
            self.logger.error("Failed to cleanup old backups: %s", e)

    def _restore_migration_backup(self):
        """Restore from migration backup"""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    "SELECT backup_path FROM migration_backups ORDER BY created_at DESC LIMIT 1"
                )
                result = cursor.fetchone()

                if not result:
                    raise DatabaseError(message="No migration backup found to restore")

                backup_path = result[0]
                self._verify_db_integrity(backup_path)
                shutil.copy2(backup_path, self.db_path)
                self._verify_db_integrity(self.db_path)
                self.logger.info("Restored from backup: %s", backup_path)
        except Exception as e:
            self.logger.exception("Failed to restore migration backup")
            raise DatabaseError(message="Failed to restore migration backup", cause=e)

    def _verify_db_integrity(self, db_path: str) -> None:
        if not db_path or not isinstance(db_path, str):
            raise ValidationError(message="Invalid db_path")
        try:
            with sqlite3.connect(db_path, timeout=DB_CONNECTION_TIMEOUT) as conn:
                row = conn.execute("PRAGMA integrity_check").fetchone()
                value = None
                if row:
                    value = row[0]
                if str(value).lower() != "ok":
                    raise DatabaseError(
                        message="Database integrity_check failed",
                        details={"db_path": db_path, "result": value},
                    )
        except DatabaseError:
            raise
        except Exception as e:
            raise DatabaseError(
                message="Database integrity_check failed",
                details={"db_path": db_path},
                cause=e,
            )

    def _migration_001_analytics_columns(self, conn) -> List[Dict]:
        """Migration 1: Add analytics columns to tasks table"""
        migrations_applied = []

        try:
            # Check if analytics columns exist
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]

            # Add missing analytics columns
            analytics_columns = [
                ("completed_at", "TIMESTAMP"),
                ("struck_today", "BOOLEAN DEFAULT 0"),
                ("struck_date", "TIMESTAMP"),
                ("strike_report", "TEXT"),
                ("strike_count", "INTEGER DEFAULT 0"),
            ]

            # Issue #8: Avoid f-strings in SQL, validate against whitelist
            for column_name, column_def in analytics_columns:
                if column_name not in columns:
                    # Validate column_name is in whitelist (all defined above)
                    if column_name in [col[0] for col in analytics_columns]:
                        # Safe to use f-string since validated against hardcoded whitelist
                        conn.execute(
                            f"ALTER TABLE tasks ADD COLUMN {column_name} {column_def}"
                        )
                        self.logger.info("Added %s column to tasks table", column_name)
                    migrations_applied.append(
                        {
                            "version": 1,
                            "description": f"Added {column_name} column",
                            "sql": f"ALTER TABLE tasks ADD COLUMN {column_name} {column_def}",
                        }
                    )

            return migrations_applied

        except Exception as e:
            self.logger.error(f"Migration 001 failed: {e}")
            raise

    def _migration_002_indexes_constraints(self, conn) -> List[Dict]:
        """Migration 2: Add indexes and constraints for performance"""
        migrations_applied = []

        try:
            # Add performance indexes
            indexes = [
                (
                    "idx_tasks_user_status",
                    "CREATE INDEX IF NOT EXISTS idx_tasks_user_status ON tasks (user_id, status)",
                ),
                (
                    "idx_tasks_user_priority",
                    "CREATE INDEX IF NOT EXISTS idx_tasks_user_priority ON tasks (user_id, priority)",
                ),
                (
                    "idx_tasks_user_created",
                    "CREATE INDEX IF NOT EXISTS idx_tasks_user_created ON tasks (user_id, created_at)",
                ),
                (
                    "idx_tasks_user_due",
                    "CREATE INDEX IF NOT EXISTS idx_tasks_user_due ON tasks (user_id, due_date)",
                ),
                (
                    "idx_tasks_completed",
                    "CREATE INDEX IF NOT EXISTS idx_tasks_completed ON tasks (completed_at)",
                ),
                (
                    "idx_tasks_struck",
                    "CREATE INDEX IF NOT EXISTS idx_tasks_struck ON tasks (struck_date)",
                ),
            ]

            for index_name, sql in indexes:
                conn.execute(sql)
                self.logger.info(f"Created index: {index_name}")
                migrations_applied.append(
                    {
                        "version": 2,
                        "description": f"Created index {index_name}",
                        "sql": sql,
                    }
                )

            return migrations_applied

        except Exception as e:
            self.logger.error(f"Migration 002 failed: {e}")
            raise

    def _migration_003_user_preferences(self, conn) -> List[Dict]:
        """Migration 3: Add user preferences table"""
        migrations_applied = []

        try:
            # Create user preferences table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    theme TEXT DEFAULT 'orange',
                    dpi_scale INTEGER DEFAULT 100,
                    autosave_interval INTEGER DEFAULT 30,
                    notifications BOOLEAN DEFAULT 1,
                    daily_reset_time TEXT DEFAULT '09:00',
                    timezone TEXT DEFAULT 'UTC',
                    language TEXT DEFAULT 'en',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """)

            self.logger.info("Created user_preferences table")
            migrations_applied.append(
                {
                    "version": 3,
                    "description": "Created user_preferences table",
                    "sql": "CREATE TABLE user_preferences",
                }
            )

            return migrations_applied

        except Exception as e:
            self.logger.error(f"Migration 003 failed: {e}")
            raise

    def _migration_004_audit_trail(self, conn) -> List[Dict]:
        """Migration 4: Add audit trail table"""
        migrations_applied = []

        try:
            # Create audit trail table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_trail (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    table_name TEXT NOT NULL,
                    record_id TEXT,
                    old_values TEXT,
                    new_values TEXT,
                    ip_address TEXT,
                    user_agent TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """)

            # Create index for audit trail
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_user_action ON audit_trail (user_id, action)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_trail (created_at)"
            )

            self.logger.info("Created audit_trail table")
            migrations_applied.append(
                {
                    "version": 4,
                    "description": "Created audit_trail table",
                    "sql": "CREATE TABLE audit_trail",
                }
            )

            return migrations_applied

        except Exception as e:
            self.logger.error(f"Migration 004 failed: {e}")
            raise

    def _migration_005_planner_v2(self, conn) -> List[Dict]:
        """Migration 5: Add planner v2 tables"""
        migrations_applied = []

        try:
            # Create planner_v2_schedule table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS planner_v2_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    scheduled_tasks TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id)
                )
            """)

            # Create index for better performance
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_planner_v2_user_id ON planner_v2_schedule (user_id)"
            )

            self.logger.info("Created planner_v2_schedule table")
            migrations_applied.append(
                {
                    "version": 5,
                    "description": "Created planner_v2_schedule table",
                    "sql": "CREATE TABLE planner_v2_schedule",
                }
            )

            return migrations_applied

        except Exception as e:
            self.logger.error(f"Migration 005 failed: {e}")
            raise

    def _migration_006_scheduled_fields(self, conn) -> List[Dict]:
        """Migration 6: Add scheduled_date and scheduled_minute fields to tasks table"""
        migrations_applied = []

        try:
            # Check if scheduled_date and scheduled_minute columns exist
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]

            # Add scheduled_minute column if it doesn't exist
            if "scheduled_minute" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN scheduled_minute INTEGER")
                migrations_applied.append(
                    {
                        "version": 6,
                        "name": "add_scheduled_minute_column",
                        "description": "Add scheduled_minute column to tasks table",
                    }
                )
                self.logger.info("Added scheduled_minute column to tasks table")

            # Add scheduled_date column if it doesn't exist
            if "scheduled_date" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN scheduled_date TEXT")
                migrations_applied.append(
                    {
                        "version": 6,
                        "name": "add_scheduled_date_column",
                        "description": "Add scheduled_date column to tasks table",
                    }
                )
                self.logger.info("Added scheduled_date column to tasks table")

            return migrations_applied

        except Exception as e:
            self.logger.error(f"Migration 006 failed: {e}")
            raise

    def _migration_007_daily_strikes(self, conn) -> List[Dict]:
        """Migration 7: Add daily_strikes TEXT column to tasks for per-day strike tracking"""
        migrations_applied = []
        try:
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]
            if "daily_strikes" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN daily_strikes TEXT")
                migrations_applied.append(
                    {
                        "version": 7,
                        "name": "add_daily_strikes_column",
                        "description": "Add daily_strikes TEXT column to tasks table",
                    }
                )
                self.logger.info("Added daily_strikes column to tasks table")
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 007 failed: {e}")
            raise

    def _migration_008_planner_history(self, conn) -> List[Dict]:
        migrations_applied = []
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS planner_task_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    day TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    title TEXT,
                    scheduled_hour INTEGER,
                    scheduled_minute INTEGER,
                    scheduled_duration INTEGER,
                    strike_mode TEXT DEFAULT 'none',
                    strikes_for_day INTEGER DEFAULT 0,
                    completed BOOLEAN DEFAULT 0,
                    strike_report TEXT,
                    captured_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_planner_history_user_day ON planner_task_history (user_id, day)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_planner_history_day ON planner_task_history (day)"
            )

            self.logger.info("Created planner_task_history table")
            migrations_applied.append(
                {
                    "version": 8,
                    "description": "Created planner_task_history table",
                    "sql": "CREATE TABLE planner_task_history",
                }
            )
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 008 failed: {e}")
            raise

    def _migration_009_strike_report_history(self, conn) -> List[Dict]:
        migrations_applied = []
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strike_today_report_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    day TEXT NOT NULL,
                    strike_number INTEGER NOT NULL,
                    report TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_strike_report_user_task ON strike_today_report_history (user_id, task_id, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_strike_report_user_day ON strike_today_report_history (user_id, day)"
            )

            self.logger.info("Created strike_today_report_history table")
            migrations_applied.append(
                {
                    "version": 9,
                    "description": "Created strike_today_report_history table",
                    "sql": "CREATE TABLE strike_today_report_history",
                }
            )
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 009 failed: {e}")
            raise

    def _migration_010_struck_forever(self, conn) -> List[Dict]:
        """Migration 10: Add struck_forever BOOLEAN column to tasks table (backward compatible)."""
        migrations_applied = []
        try:
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]

            if "struck_forever" not in columns:
                conn.execute(
                    "ALTER TABLE tasks ADD COLUMN struck_forever BOOLEAN DEFAULT 0"
                )
                self.logger.info("Added struck_forever column to tasks table")

            migrations_applied.append(
                {
                    "version": 10,
                    "description": "Added struck_forever column to tasks",
                    "sql": "ALTER TABLE tasks ADD COLUMN struck_forever",
                }
            )
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 010 failed: {e}")
            raise

    def _migration_011_analytics_history(self, conn) -> List[Dict]:
        migrations_applied = []
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS strike_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    day TEXT NOT NULL,
                    strike_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_strike_events_user_day ON strike_events (user_id, day)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_strike_events_user_task ON strike_events (user_id, task_id, created_at)"
            )

            conn.execute("""
                CREATE TABLE IF NOT EXISTS settings_change_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    day TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_settings_change_events_user_day ON settings_change_events (user_id, day)"
            )

            conn.execute("""
                CREATE TABLE IF NOT EXISTS recap_seen (
                    user_id TEXT NOT NULL,
                    recap_day TEXT NOT NULL,
                    seen_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, recap_day),
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """)

            migrations_applied.append(
                {
                    "version": 11,
                    "description": "Created strike_events, settings_change_events, recap_seen tables",
                    "sql": "CREATE TABLE strike_events/settings_change_events/recap_seen",
                }
            )
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 011 failed: {e}")
            raise

    def _migration_012_refreshed_at(self, conn) -> List[Dict[str, Any]]:
        """Migration 012: Add refreshed_at column to tasks table for daily reset badge"""
        migrations_applied = []
        try:
            # Check if column already exists
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]

            if "refreshed_at" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN refreshed_at TEXT")
                self.logger.info("Added refreshed_at column to tasks table")

                migrations_applied.append(
                    {
                        "version": 12,
                        "description": "Added refreshed_at column to tasks table",
                        "sql": "ALTER TABLE tasks ADD COLUMN refreshed_at TEXT",
                    }
                )
            else:
                self.logger.info(
                    "refreshed_at column already exists, skipping migration 012"
                )

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 012 failed: {e}")
            raise

    def _get_connection(self):
        """Get a database connection with proper configuration"""
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
            conn.row_factory = sqlite3.Row  # Enable dict-like access
            conn.execute("SELECT 1")
        except Exception as e:
            try:
                conn.close()
            except Exception:  # noqa: broad-except - Data layer defensive exception handling
                self.logger.exception("Failed to close unhealthy connection")
            raise DatabaseError(
                message="Database connection health check failed",
                details={"db_path": self.db_path},
                cause=e,
            )
        return conn

    def _ensure_user_exists(self, user_id: str) -> bool:
        """Ensure user exists in database, create if not"""
        try:
            with self._get_connection() as conn:
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

    def _validate_task(self, task: Dict[str, Any]) -> bool:
        """Validate a single task"""
        required_fields = ["id", "title"]
        for field in required_fields:
            if field not in task:
                self.logger.error(f"Task missing required field: {field}")
                return False

        # Validate title
        if not isinstance(task["title"], str) or len(task["title"]) > 200:
            self.logger.error(f"Invalid title: {task['title']}")
            return False

        # Validate ID
        if not isinstance(task["id"], str) or len(task["id"]) == 0:
            self.logger.error(f"Invalid task ID: {task['id']}")
            return False

        # Validate completion status
        if "completed" in task and not isinstance(task["completed"], bool):
            self.logger.error(f"Invalid completion status: {task['completed']}")
            return False

        return True

    def _validate_tasks(self, tasks: List[Dict[str, Any]]) -> bool:
        """Validate all tasks"""
        from src.constants import MAX_TASKS_PER_USER

        if not isinstance(tasks, list):
            self.logger.error("Tasks must be a list")
            return False

        if len(tasks) > MAX_TASKS_PER_USER:
            self.logger.error(
                f"Too many tasks provided: {len(tasks)} (max {MAX_TASKS_PER_USER})"
            )
            return False

        # Check for duplicate IDs
        task_ids = set()
        for task in tasks:
            if not self._validate_task(task):
                return False

            if task["id"] in task_ids:
                self.logger.error(f"Duplicate task ID: {task['id']}")
                return False
            task_ids.add(task["id"])

        return True

    def _task_dict_to_row(self, task: Dict[str, Any], user_id: str) -> tuple:
        """Convert task dictionary to database row.

        NOTE: The column order here must match all INSERT column lists that
        reference it. New columns should be appended here and in those
        statements in lock-step.
        """
        task = self._normalize_task_dict(task)
        return (
            task["id"],
            user_id,
            task["title"],
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
            task.get("recurrence_type") or None,
            task.get("recurrence_param"),
            task.get("snoozed_until"),
            json.dumps(task.get("subtasks") or []),
            task.get("created_at", datetime.now().isoformat()),
            task.get("updated_at", datetime.now().isoformat()),
        )

    def _row_to_task_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert database row to task dictionary"""
        # Safely parse daily_strikes JSON if present
        daily_strikes = {}
        try:
            raw = row["daily_strikes"] if "daily_strikes" in row.keys() else None
            if raw:
                daily_strikes = json.loads(raw)
        except Exception:  # noqa: broad-except - Data layer defensive exception handling
            daily_strikes = {}

        # Optional recurrence/snooze fields may not exist on very old schemas.
        keys = row.keys()
        recurrence_type = row["recurrence_type"] if "recurrence_type" in keys else None
        recurrence_param = (
            row["recurrence_param"] if "recurrence_param" in keys else None
        )
        snoozed_until = row["snoozed_until"] if "snoozed_until" in keys else None

        # Subtasks (JSON array)
        subtasks = []
        try:
            raw_sub = row["subtasks"] if "subtasks" in keys else None
            if raw_sub:
                subtasks = json.loads(raw_sub)
                if not isinstance(subtasks, list):
                    subtasks = []
        except Exception:  # noqa: broad-except
            subtasks = []

        return {
            "id": row["id"],
            "title": row["title"],
            "description": row["description"] or "",
            "project": row["project"] or "",
            "owner": row["owner"] if "owner" in keys else "",
            "priority": row["priority"] or "medium",
            "status": row["status"] or "pending",
            "completed": bool(row["completed"]),
            "completed_at": row["completed_at"],
            "due_date": row["due_date"],
            "estimated_duration": row["estimated_duration"] or 60,
            "scheduled_hour": row["scheduled_hour"],
            "scheduled_minute": row["scheduled_minute"]
            if "scheduled_minute" in keys
            else None,
            "scheduled_date": row["scheduled_date"]
            if "scheduled_date" in keys
            else None,
            "scheduled_duration": row["scheduled_duration"],
            "struck_forever": bool(
                row["struck_forever"] if "struck_forever" in keys else False
            ),
            "struck_today": bool(
                row["struck_today"] if "struck_today" in keys else False
            ),
            "struck_date": row["struck_date"] if "struck_date" in keys else None,
            "strike_report": row["strike_report"] if "strike_report" in keys else None,
            "strike_count": row["strike_count"] if "strike_count" in keys else 0,
            "daily_strikes": daily_strikes,
            "refreshed_at": row["refreshed_at"] if "refreshed_at" in keys else None,
            "recurrence_type": recurrence_type,
            "recurrence_param": recurrence_param,
            "snoozed_until": snoozed_until,
            "subtasks": subtasks,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "archived_at": row["archived_at"] if "archived_at" in keys else None,
            "parent_id": row["parent_id"] if "parent_id" in keys else None,
        }

    # Task Management Methods
    def load_tasks_for_user(self, user_id: str) -> Optional[List[Dict[str, Any]]]:
        """Load all active, struck, and archived tasks for a specific user from database.

        Returns active tasks, struck tasks (today/forever), and archived completed tasks
        so that all tasks are visible in the UI regardless of archival status.
        """
        try:
            self._ensure_user_exists(user_id)

            with self.pooled_connection() as conn:
                conn.execute("BEGIN")

                try:
                    cursor = conn.execute(
                        """
                        SELECT * FROM tasks
                        WHERE user_id = ? AND (completed = 0 OR struck_today = 1 OR struck_forever = 1)
                        ORDER BY created_at DESC
                    """,
                        (user_id,),
                    )

                    rows = cursor.fetchall()

                    tasks = []
                    for row in rows:
                        try:
                            task_dict = self._row_to_task_dict(row)
                            if self._validate_task(task_dict):
                                tasks.append(task_dict)
                            else:
                                self.logger.warning(
                                    "Invalid task data found for user %s, skipping corrupted task",
                                    user_id,
                                )
                        except Exception as row_e:
                            self.logger.warning(
                                "Failed to convert row for user %s: %s", user_id, row_e
                            )
                            continue


                    conn.commit()
                    self.logger.info(
                        "Successfully loaded %d tasks for user %s", len(tasks), user_id
                    )
                    return tasks
                except Exception as inner_e:
                    try:
                        conn.rollback()
                    except Exception:  # noqa: broad-except - Data layer defensive exception handling
                        self.logger.exception("Rollback failed for user %s", user_id)
                    self.logger.exception("Transaction failed for user %s", user_id)
                    raise

        except Exception as e:
            self.logger.exception("Error loading tasks for user %s", user_id)
            raise DatabaseError(
                message=f"Error loading tasks for user {user_id}",
                cause=e,
            )

    def save_tasks_for_user(self, user_id: str, tasks: List[Dict[str, Any]]) -> bool:
        """Save only active (non-completed) tasks for a specific user to database with UPSERT pattern.

        This method filters out completed tasks automatically. Completed tasks should be
        archived using the archive_task() method. Only tasks with completed=False will be saved.
        """
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                with self._lock:
                    tasks_normalized = [
                        self._normalize_task_dict(t) for t in (tasks or [])
                    ]

                    if not self._validate_tasks(tasks_normalized):
                        self.logger.error(f"Task validation failed for user {user_id}")
                        return False

                    self._ensure_user_exists(user_id)

                    with self._get_connection() as conn:
                        conn.execute("BEGIN IMMEDIATE TRANSACTION")

                        try:
                            # Filter to only include active (non-completed) tasks
                            active_tasks = [
                                t
                                for t in tasks_normalized
                                if not t.get("completed", False)
                            ]

                            # First, delete all active tasks for this user from the tasks table
                            # We'll re-insert only the active ones. Completed tasks are archived separately.
                            conn.execute(
                                "DELETE FROM tasks WHERE user_id = ? AND completed = 0",
                                (user_id,),
                            )

                            # Use UPSERT (INSERT OR REPLACE) for active tasks
                            # This is more efficient and safer
                            for task in active_tasks:
                                task_row = self._task_dict_to_row(task, user_id)
                                conn.execute(
                                    """
                                    INSERT INTO tasks (
                                        id, user_id, title, description, project, owner, priority, status,
                                        completed, completed_at, due_date, estimated_duration, scheduled_hour,
                                        scheduled_minute, scheduled_date, scheduled_duration, struck_forever, struck_today, struck_date, strike_report, strike_count,
                                        daily_strikes, refreshed_at, recurrence_type, recurrence_param, snoozed_until, subtasks, created_at, updated_at
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                    task_row,
                                )

                            # Verify count matches active tasks only
                            count_cursor = conn.execute(
                                "SELECT COUNT(*) FROM tasks WHERE user_id = ? AND completed = 0",
                                (user_id,),
                            )
                            inserted_count = count_cursor.fetchone()[0]

                            if inserted_count != len(active_tasks):
                                raise Exception(
                                    f"Count verification failed: expected {len(active_tasks)}, got {inserted_count}"
                                )

                            conn.commit()
                            self.logger.info(
                                f"Successfully saved {len(active_tasks)} active tasks for user {user_id} (skipped {len(tasks_normalized) - len(active_tasks)} completed tasks)"
                            )
                            return True

                        except Exception as inner_e:
                            conn.rollback()
                            self.logger.error(
                                f"Transaction failed for user {user_id}, attempt {attempt + 1}: {inner_e}"
                            )
                            raise

            except Exception as e:
                self.logger.error(
                    f"Error saving tasks for user {user_id}, attempt {attempt + 1}: {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2**attempt))
                    continue
                return False

        return False

    def create_task_for_user(
        self, user_id: str, task_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create a single task for a user with transaction safety.

        This method also enforces a per-user duplicate check on (title, project)
        for active (non-completed) tasks, unless the caller explicitly passes
        ignore_duplicate=True in the task_data payload.
        """
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                with self._lock:
                    self._ensure_user_exists(user_id)

                    if task_data is None or not isinstance(task_data, dict):
                        return None

                    # Optional flag used by the UI when the user chooses
                    # "Add again" for a duplicate task. This flag is NOT
                    # persisted to the database and only affects the duplicate
                    # check logic below.
                    ignore_duplicate = bool(task_data.pop("ignore_duplicate", False))

                    if "id" not in task_data:
                        task_data["id"] = str(uuid.uuid4())

                    task_data = self._normalize_task_dict(task_data)

                    if not self._validate_task(task_data):
                        self.logger.error(f"Task validation failed for user {user_id}")
                        return None

                    with self._get_connection() as conn:
                        conn.execute("BEGIN IMMEDIATE TRANSACTION")

                        try:
                            # Duplicate guard: if ignore_duplicate is False, check
                            # for an existing active task with the same
                            # case-insensitive title + project (treat NULL/empty
                            # project as equivalent).
                            if not ignore_duplicate:
                                title = (task_data.get("title") or "").strip()
                                project_raw = (task_data.get("project") or "").strip()
                                project_key = project_raw.lower()

                                if title:
                                    cursor = conn.execute(
                                        """
                                        SELECT id FROM tasks
                                        WHERE user_id = ?
                                          AND LOWER(title) = LOWER(?)
                                          AND LOWER(COALESCE(project, '')) = ?
                                          AND completed = 0
                                        LIMIT 1
                                        """,
                                        (user_id, title, project_key),
                                    )
                                    existing = cursor.fetchone()
                                    if existing:
                                        self.logger.info(
                                            "Duplicate task detected for user %s (title=%r, project=%r), creation skipped",
                                            user_id,
                                            title,
                                            project_raw,
                                        )
                                        conn.rollback()
                                        return None

                            task_row = self._task_dict_to_row(task_data, user_id)
                            conn.execute(
                                """
                                INSERT INTO tasks (
                                    id, user_id, title, description, project, owner, priority, status,
                                    completed, completed_at, due_date, estimated_duration, scheduled_hour,
                                    scheduled_minute, scheduled_date, scheduled_duration, struck_forever, struck_today, struck_date, strike_report, strike_count,
                                    daily_strikes, refreshed_at, recurrence_type, recurrence_param, snoozed_until, subtasks, created_at, updated_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                                task_row,
                            )

                            conn.commit()

                            cursor = conn.execute(
                                "SELECT * FROM tasks WHERE id = ?", (task_data["id"],)
                            )
                            row = cursor.fetchone()
                            if row:
                                created_task = self._row_to_task_dict(row)
                                self.logger.info(
                                    f"Successfully created task {task_data['id']} for user {user_id}"
                                )
                                return created_task
                            raise Exception("Task not found after creation")

                        except sqlite3.IntegrityError as ie:
                            conn.rollback()
                            self.logger.error(
                                f"Integrity error creating task for user {user_id}: {ie}"
                            )
                            return None
                        except Exception as inner_e:
                            conn.rollback()
                            self.logger.error(
                                f"Transaction failed for user {user_id}, attempt {attempt + 1}: {inner_e}"
                            )
                            raise

            except Exception as e:
                self.logger.error(
                    f"Error creating task for user {user_id}, attempt {attempt + 1}: {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2**attempt))
                    continue
                return None

        return None

    def get_task_by_id(self, user_id: str, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific task by ID (Issue #6 - avoid N+1 query problem)"""
        try:
            with self.pooled_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
                    (task_id, user_id),
                )
                row = cursor.fetchone()

                if row:
                    return self._row_to_task_dict(row)
                return None
        except Exception as e:
            self.logger.exception("Error getting task %s for user %s", task_id, user_id)
            raise DatabaseError(
                message=f"Error getting task {task_id} for user {user_id}", cause=e
            )

    def bulk_create_tasks(self, user_id: str, tasks: List[Dict[str, Any]]) -> bool:
        """Bulk create tasks without loading existing tasks (Issue #12)"""
        try:
            self._ensure_user_exists(user_id)

            if not isinstance(tasks, list) or len(tasks) > 200:
                self.logger.error(
                    f"Too many tasks for bulk_create_tasks: {0 if not isinstance(tasks, list) else len(tasks)} (max 200)"
                )
                return False

            # Validate all tasks
            for task in tasks:
                if "id" not in task:
                    task["id"] = str(uuid.uuid4())
                if not self._validate_task(task):
                    raise DataManagerException(
                        f"Task validation failed: {task.get('title', 'unknown')}"
                    )

            with self.pooled_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")

                try:
                    task_rows = [
                        self._task_dict_to_row(task, user_id) for task in tasks
                    ]
                    conn.executemany(
                        """
                        INSERT INTO tasks (
                            id, user_id, title, description, project, owner, priority, status,
                            completed, completed_at, due_date, estimated_duration, scheduled_hour,
                            scheduled_minute, scheduled_date, scheduled_duration, struck_forever, struck_today,
                            struck_date, strike_report, strike_count, daily_strikes, refreshed_at, recurrence_type, recurrence_param, snoozed_until, subtasks, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        task_rows,
                    )

                    conn.commit()
                    self.logger.info(
                        "Bulk created %d tasks for user %s", len(tasks), user_id
                    )
                    return True

                except Exception as inner_e:
                    try:
                        conn.rollback()
                    except Exception:  # noqa: broad-except - Data layer defensive exception handling
                        self.logger.exception(
                            "Rollback failed during bulk_create_tasks"
                        )
                    raise DatabaseError(message="Bulk insert failed", cause=inner_e)

        except Exception as e:
            self.logger.exception("Error bulk creating tasks for user %s", user_id)
            raise DatabaseError(
                message=f"Error bulk creating tasks for user {user_id}", cause=e
            )

    def update_task_for_user(
        self, user_id: str, task_id: str, task_data: Dict[str, Any]
    ) -> bool:
        """Update a specific task for a user with transaction safety"""
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                with self._lock:
                    with self._get_connection() as conn:
                        conn.execute("BEGIN IMMEDIATE TRANSACTION")

                        backup_row = None
                        try:
                            # Single query: Get full task and check existence
                            cursor = conn.execute(
                                "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
                                (task_id, user_id),
                            )
                            backup_row = cursor.fetchone()

                            if not backup_row:
                                self.logger.error(
                                    f"Task {task_id} not found for user {user_id}"
                                )
                                conn.rollback()
                                return False

                            existing_task = self._row_to_task_dict(backup_row)
                            merged_task = {**existing_task, **(task_data or {})}
                            merged_task = self._normalize_task_dict(merged_task)

                            conn.execute(
                                """
                                UPDATE tasks SET
                                    title = ?, description = ?, project = ?, owner = ?, priority = ?,
                                    status = ?, completed = ?, completed_at = ?, due_date = ?, estimated_duration = ?,
                                    scheduled_hour = ?, scheduled_minute = ?, scheduled_date = ?, scheduled_duration = ?,
                                    struck_forever = ?, struck_today = ?, struck_date = ?,
                                    strike_report = ?, strike_count = ?, daily_strikes = ?, refreshed_at = ?,
                                    recurrence_type = ?, recurrence_param = ?, snoozed_until = ?, subtasks = ?, updated_at = ?
                                WHERE id = ? AND user_id = ?
                                """,
                                (
                                    merged_task.get("title", ""),
                                    merged_task.get("description", ""),
                                    merged_task.get("project", ""),
                                    merged_task.get("owner", ""),
                                    merged_task.get("priority", "medium"),
                                    merged_task.get("status", "pending"),
                                    merged_task.get("completed", False),
                                    merged_task.get("completed_at"),
                                    merged_task.get("due_date"),
                                    merged_task.get("estimated_duration", 60),
                                    merged_task.get("scheduled_hour"),
                                    merged_task.get("scheduled_minute"),
                                    merged_task.get("scheduled_date"),
                                    merged_task.get("scheduled_duration"),
                                    merged_task.get("struck_forever", False),
                                    merged_task.get("struck_today", False),
                                    merged_task.get("struck_date"),
                                    merged_task.get("strike_report"),
                                    merged_task.get("strike_count", 0),
                                    json.dumps(merged_task.get("daily_strikes", {})),
                                    merged_task.get("refreshed_at"),
                                    merged_task.get("recurrence_type") or None,
                                    merged_task.get("recurrence_param"),
                                    merged_task.get("snoozed_until"),
                                    json.dumps(merged_task.get("subtasks") or []),
                                    datetime.now().isoformat(),
                                    task_id,
                                    user_id,
                                ),
                            )

                            verify_cursor = conn.execute(
                                "SELECT COUNT(*) FROM tasks WHERE id = ? AND user_id = ?",
                                (task_id, user_id),
                            )
                            if verify_cursor.fetchone()[0] != 1:
                                raise Exception("Task update verification failed")

                            conn.commit()
                            self.logger.info(
                                f"Successfully updated task {task_id} for user {user_id}"
                            )
                            return True

                        except Exception as inner_e:
                            conn.rollback()
                            self.logger.error(
                                f"Transaction failed for user {user_id}, task {task_id}, attempt {attempt + 1}: {inner_e}"
                            )

                            if attempt == max_retries - 1 and backup_row:
                                try:
                                    self.logger.warning(
                                        f"Restoring backup for task {task_id} after final failure"
                                    )
                                    conn.execute("BEGIN IMMEDIATE TRANSACTION")
                                    conn.execute(
                                        "DELETE FROM tasks WHERE id = ? AND user_id = ?",
                                        (task_id, user_id),
                                    )
                                    backup_task = self._row_to_task_dict(backup_row)
                                    backup_row_tuple = self._task_dict_to_row(
                                        backup_task, user_id
                                    )
                                    conn.execute(
                                        """
                                        INSERT INTO tasks (
                                            id, user_id, title, description, project, owner, priority, status,
                                            completed, completed_at, due_date, estimated_duration, scheduled_hour,
                                            scheduled_minute, scheduled_date, scheduled_duration, struck_forever, struck_today, struck_date, strike_report, strike_count,
                                            daily_strikes, refreshed_at, recurrence_type, recurrence_param, snoozed_until, subtasks, created_at, updated_at
                                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                        """,
                                        backup_row_tuple,
                                    )
                                    conn.commit()
                                    self.logger.info(
                                        f"Backup restored for task {task_id}"
                                    )
                                except Exception as restore_e:
                                    conn.rollback()
                                    self.logger.error(
                                        f"Failed to restore backup for task {task_id}: {restore_e}"
                                    )

                            raise

            except Exception as e:
                self.logger.error(
                    f"Error updating task {task_id} for user {user_id}, attempt {attempt + 1}: {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2**attempt))
                    continue
                return False

        return False

    def delete_task_for_user(self, user_id: str, task_id: str) -> bool:
        """Delete a specific task for a user from either active or archived tasks.

        This method will attempt to delete from the tasks table first, then from archived_tasks.
        Returns True if the task was found and deleted from either table.
        """
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                with self._lock:
                    with self._get_connection() as conn:
                        conn.execute("BEGIN IMMEDIATE TRANSACTION")

                        backup_row = None
                        deleted_from_table = None
                        try:
                            # Try to find task in active tasks first
                            backup_cursor = conn.execute(
                                "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
                                (task_id, user_id),
                            )
                            backup_row = backup_cursor.fetchone()

                            # If not in active tasks, try archived tasks
                            if not backup_row:
                                backup_cursor = conn.execute(
                                    "SELECT * FROM archived_tasks WHERE id = ? AND user_id = ?",
                                    (task_id, user_id),
                                )
                                backup_row = backup_cursor.fetchone()
                                deleted_from_table = "archived_tasks"
                            else:
                                deleted_from_table = "tasks"

                            if not backup_row:
                                self.logger.warning(
                                    f"Task {task_id} not found in either tasks or archived_tasks for user {user_id}"
                                )
                                conn.rollback()
                                return False

                            # Delete from the appropriate table
                            if deleted_from_table == "tasks":
                                conn.execute(
                                    "DELETE FROM tasks WHERE id = ? AND user_id = ?",
                                    (task_id, user_id),
                                )
                                verify_cursor = conn.execute(
                                    "SELECT COUNT(*) FROM tasks WHERE id = ? AND user_id = ?",
                                    (task_id, user_id),
                                )
                            else:
                                conn.execute(
                                    "DELETE FROM archived_tasks WHERE id = ? AND user_id = ?",
                                    (task_id, user_id),
                                )
                                verify_cursor = conn.execute(
                                    "SELECT COUNT(*) FROM archived_tasks WHERE id = ? AND user_id = ?",
                                    (task_id, user_id),
                                )

                            if verify_cursor.fetchone()[0] != 0:
                                raise Exception("Task deletion verification failed")

                            conn.commit()
                            self.logger.info(
                                f"Successfully deleted task {task_id} for user {user_id} from {deleted_from_table}"
                            )
                            return True

                        except Exception as inner_e:
                            conn.rollback()
                            self.logger.error(
                                f"Transaction failed for user {user_id}, task {task_id}, attempt {attempt + 1}: {inner_e}"
                            )

                            if (
                                attempt == max_retries - 1
                                and backup_row
                                and deleted_from_table
                            ):
                                try:
                                    self.logger.warning(
                                        f"Restoring backup for task {task_id} after final failure to {deleted_from_table}"
                                    )
                                    conn.execute("BEGIN IMMEDIATE TRANSACTION")
                                    backup_task = self._row_to_task_dict(backup_row)
                                    backup_row_tuple = self._task_dict_to_row(
                                        backup_task, user_id
                                    )

                                    if deleted_from_table == "tasks":
                                        conn.execute(
                                            """
                                            INSERT INTO tasks (
                                                id, user_id, title, description, project, owner, priority, status,
                                                completed, completed_at, due_date, estimated_duration, scheduled_hour,
                                                scheduled_minute, scheduled_date, scheduled_duration, struck_forever, struck_today, struck_date, strike_report, strike_count,
                                                daily_strikes, refreshed_at, recurrence_type, recurrence_param, snoozed_until, subtasks, created_at, updated_at
                                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                            """,
                                            backup_row_tuple,
                                        )
                                    else:  # archived_tasks
                                        # Restore to archived_tasks with archived_at timestamp
                                        archive_row = backup_row_tuple + (
                                            backup_row.get(
                                                "archived_at",
                                                datetime.now().isoformat(),
                                            ),
                                        )
                                        conn.execute(
                                            """
                                            INSERT INTO archived_tasks (
                                                id, user_id, title, description, project, owner, priority, status,
                                                completed, completed_at, due_date, estimated_duration, scheduled_hour,
                                                scheduled_minute, scheduled_date, scheduled_duration, struck_forever, struck_today, struck_date, strike_report, strike_count,
                                                daily_strikes, refreshed_at, recurrence_type, recurrence_param, snoozed_until, subtasks, created_at, updated_at, archived_at
                                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                            """,
                                            archive_row,
                                        )

                                    conn.commit()
                                    self.logger.info(
                                        f"Backup restored for task {task_id} to {deleted_from_table}"
                                    )
                                except Exception as restore_e:
                                    conn.rollback()
                                    self.logger.error(
                                        f"Failed to restore backup for task {task_id}: {restore_e}"
                                    )

                            raise

            except Exception as e:
                self.logger.error(
                    f"Error deleting task {task_id} for user {user_id}, attempt {attempt + 1}: {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2**attempt))
                    continue
                return False

        return False

    # Task Archival Methods
    def load_active_tasks_for_user(
        self, user_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Load only active (non-completed) tasks for a specific user.

        This is the new primary method for loading tasks - returns only tasks
        where completed=False. Completed tasks should be loaded via the archive methods.
        """
        try:
            self._ensure_user_exists(user_id)

            with self.pooled_connection() as conn:
                conn.execute("BEGIN")

                try:
                    cursor = conn.execute(
                        """
                        SELECT * FROM tasks
                        WHERE user_id = ? AND completed = 0
                        ORDER BY created_at DESC
                    """,
                        (user_id,),
                    )

                    rows = cursor.fetchall()

                    tasks = []
                    for row in rows:
                        try:
                            task_dict = self._row_to_task_dict(row)
                            if self._validate_task(task_dict):
                                tasks.append(task_dict)
                            else:
                                self.logger.warning(
                                    "Invalid active task data found for user %s, skipping corrupted task",
                                    user_id,
                                )
                        except Exception as row_e:
                            self.logger.warning(
                                "Failed to convert active task row for user %s: %s",
                                user_id,
                                row_e,
                            )
                            continue

                    conn.commit()
                    self.logger.info(
                        "Successfully loaded %d active tasks for user %s",
                        len(tasks),
                        user_id,
                    )
                    return tasks
                except Exception as inner_e:
                    try:
                        conn.rollback()
                    except Exception:
                        self.logger.exception("Rollback failed for user %s", user_id)
                    self.logger.exception("Transaction failed for user %s", user_id)
                    raise

        except Exception as e:
            self.logger.exception("Error loading active tasks for user %s", user_id)
            raise DatabaseError(
                message=f"Error loading active tasks for user {user_id}",
                cause=e,
            )

    def archive_task(self, user_id: str, task_id: str) -> bool:
        """Archive a completed task - move it from tasks to archived_tasks table.

        This is typically called after a task is marked as completed.
        """
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                with self._lock:
                    with self._get_connection() as conn:
                        conn.execute("BEGIN IMMEDIATE TRANSACTION")

                        try:
                            # Get the task from tasks table
                            cursor = conn.execute(
                                "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
                                (task_id, user_id),
                            )
                            task_row = cursor.fetchone()

                            if not task_row:
                                self.logger.warning(
                                    f"Task {task_id} not found for user {user_id}, may already be archived"
                                )
                                conn.rollback()
                                return False

                            # Convert to task dict
                            task_dict = self._row_to_task_dict(task_row)

                            # Ensure completed timestamp is set
                            if not task_dict.get("completed_at"):
                                task_dict["completed_at"] = datetime.now().isoformat()

                            # Prepare archive row (same as task row but with archived_at timestamp)
                            archive_row = (
                                task_dict["id"],
                                user_id,
                                task_dict.get("title", ""),
                                task_dict.get("description", ""),
                                task_dict.get("project", ""),
                                task_dict.get("owner", ""),
                                task_dict.get("priority", "medium"),
                                task_dict.get("status", "pending"),
                                task_dict.get("completed", False),
                                task_dict.get("completed_at"),
                                task_dict.get("due_date"),
                                task_dict.get("estimated_duration", 60),
                                task_dict.get("scheduled_hour"),
                                task_dict.get("scheduled_minute"),
                                task_dict.get("scheduled_date"),
                                task_dict.get("scheduled_duration"),
                                task_dict.get("struck_forever", False),
                                task_dict.get("struck_today", False),
                                task_dict.get("struck_date"),
                                task_dict.get("strike_report"),
                                task_dict.get("strike_count", 0),
                                json.dumps(task_dict.get("daily_strikes", {})),
                                task_dict.get("refreshed_at"),
                                task_dict.get("recurrence_type") or None,
                                task_dict.get("recurrence_param"),
                                task_dict.get("snoozed_until"),
                                json.dumps(task_dict.get("subtasks") or []),
                                task_dict.get("parent_id"),
                                task_dict.get("created_at", datetime.now().isoformat()),
                                task_dict.get("updated_at", datetime.now().isoformat()),
                                datetime.now().isoformat(),  # archived_at
                            )

                            # Insert into archived_tasks
                            conn.execute(
                                """
                                INSERT INTO archived_tasks (
                                    id, user_id, title, description, project, owner, priority, status,
                                    completed, completed_at, due_date, estimated_duration, scheduled_hour,
                                    scheduled_minute, scheduled_date, scheduled_duration, struck_forever, struck_today, struck_date, strike_report, strike_count,
                                    daily_strikes, refreshed_at, recurrence_type, recurrence_param, snoozed_until, subtasks, parent_id, created_at, updated_at, archived_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                                archive_row,
                            )

                            # Delete from tasks table
                            conn.execute(
                                "DELETE FROM tasks WHERE id = ? AND user_id = ?",
                                (task_id, user_id),
                            )

                            # Verify deletion from tasks
                            verify_cursor = conn.execute(
                                "SELECT COUNT(*) FROM tasks WHERE id = ? AND user_id = ?",
                                (task_id, user_id),
                            )
                            if verify_cursor.fetchone()[0] != 0:
                                raise Exception(
                                    "Task archival verification failed - task still in tasks table"
                                )

                            # Verify insertion into archived_tasks
                            verify_archive = conn.execute(
                                "SELECT COUNT(*) FROM archived_tasks WHERE id = ? AND user_id = ?",
                                (task_id, user_id),
                            )
                            if verify_archive.fetchone()[0] != 1:
                                raise Exception(
                                    "Task archival verification failed - task not in archived_tasks table"
                                )

                            conn.commit()
                            self.logger.info(
                                f"Successfully archived task {task_id} for user {user_id}"
                            )
                            return True

                        except Exception as inner_e:
                            conn.rollback()
                            self.logger.error(
                                f"Transaction failed archiving task {task_id} for user {user_id}, attempt {attempt + 1}: {inner_e}"
                            )
                            raise

            except Exception as e:
                self.logger.error(
                    f"Error archiving task {task_id} for user {user_id}, attempt {attempt + 1}: {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2**attempt))
                    continue
                return False

        return False

    def unarchive_task(self, user_id: str, task_id: str) -> bool:
        """Restore an archived task back to the active tasks table.

        Moves task from archived_tasks back to tasks table.
        """
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                with self._lock:
                    with self._get_connection() as conn:
                        conn.execute("BEGIN IMMEDIATE TRANSACTION")

                        try:
                            # Get the task from archived_tasks table
                            cursor = conn.execute(
                                "SELECT * FROM archived_tasks WHERE id = ? AND user_id = ?",
                                (task_id, user_id),
                            )
                            archived_row = cursor.fetchone()

                            if not archived_row:
                                self.logger.warning(
                                    f"Archived task {task_id} not found for user {user_id}"
                                )
                                conn.rollback()
                                return False

                            # Convert to task dict
                            task_dict = self._row_to_task_dict(archived_row)

                            # Prepare row for tasks table (without archived_at)
                            task_row = self._task_dict_to_row(task_dict, user_id)

                            # Insert into tasks
                            conn.execute(
                                """
                                INSERT INTO tasks (
                                    id, user_id, title, description, project, owner, priority, status,
                                    completed, completed_at, due_date, estimated_duration, scheduled_hour,
                                    scheduled_minute, scheduled_date, scheduled_duration, struck_forever, struck_today, struck_date, strike_report, strike_count,
                                    daily_strikes, refreshed_at, recurrence_type, recurrence_param, snoozed_until, subtasks, created_at, updated_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                                task_row,
                            )

                            # Delete from archived_tasks
                            conn.execute(
                                "DELETE FROM archived_tasks WHERE id = ? AND user_id = ?",
                                (task_id, user_id),
                            )

                            # Verify insertion into tasks
                            verify_cursor = conn.execute(
                                "SELECT COUNT(*) FROM tasks WHERE id = ? AND user_id = ?",
                                (task_id, user_id),
                            )
                            if verify_cursor.fetchone()[0] != 1:
                                raise Exception(
                                    "Task unarchival verification failed - task not in tasks table"
                                )

                            # Verify deletion from archived_tasks
                            verify_archive = conn.execute(
                                "SELECT COUNT(*) FROM archived_tasks WHERE id = ? AND user_id = ?",
                                (task_id, user_id),
                            )
                            if verify_archive.fetchone()[0] != 0:
                                raise Exception(
                                    "Task unarchival verification failed - task still in archived_tasks table"
                                )

                            conn.commit()
                            self.logger.info(
                                f"Successfully unarchived task {task_id} for user {user_id}"
                            )
                            return True

                        except Exception as inner_e:
                            conn.rollback()
                            self.logger.error(
                                f"Transaction failed unarchiving task {task_id} for user {user_id}, attempt {attempt + 1}: {inner_e}"
                            )
                            raise

            except Exception as e:
                self.logger.error(
                    f"Error unarchiving task {task_id} for user {user_id}, attempt {attempt + 1}: {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2**attempt))
                    continue
                return False

        return False

    def load_archived_tasks_for_user(
        self, user_id: str, limit: int = 100, offset: int = 0
    ) -> Optional[List[Dict[str, Any]]]:
        """Load paginated archived tasks for a specific user.

        Returns completed tasks that have been archived, ordered by archived_at descending.
        """
        try:
            self._ensure_user_exists(user_id)

            with self.pooled_connection() as conn:
                conn.execute("BEGIN")

                try:
                    cursor = conn.execute(
                        """
                        SELECT * FROM archived_tasks
                        WHERE user_id = ?
                        ORDER BY archived_at DESC
                        LIMIT ? OFFSET ?
                    """,
                        (user_id, limit, offset),
                    )

                    rows = cursor.fetchall()

                    tasks = []
                    for row in rows:
                        try:
                            task_dict = self._row_to_task_dict(row)
                            if self._validate_task(task_dict):
                                tasks.append(task_dict)
                            else:
                                self.logger.warning(
                                    "Invalid archived task data found for user %s, skipping corrupted task",
                                    user_id,
                                )
                        except Exception as row_e:
                            self.logger.warning(
                                "Failed to convert archived task row for user %s: %s",
                                user_id,
                                row_e,
                            )
                            continue

                    conn.commit()
                    self.logger.info(
                        "Successfully loaded %d archived tasks for user %s (offset=%d)",
                        len(tasks),
                        user_id,
                        offset,
                    )
                    return tasks
                except Exception as inner_e:
                    try:
                        conn.rollback()
                    except Exception:
                        self.logger.exception("Rollback failed for user %s", user_id)
                    self.logger.exception("Transaction failed for user %s", user_id)
                    raise

        except Exception as e:
            self.logger.exception("Error loading archived tasks for user %s", user_id)
            raise DatabaseError(
                message=f"Error loading archived tasks for user {user_id}",
                cause=e,
            )

    def load_struck_archived_tasks_for_user(self, user_id: str) -> Optional[List[Dict[str, Any]]]:
        """Load struck archived tasks for a specific user (for 'Show Archived' button).

        Returns only archived tasks that are struck (struck_today or struck_forever),
        ordered by created_at descending. These tasks will appear at the bottom of the
        completed filter after regular struck tasks, as they have the archived_at field set.
        """
        try:
            self._ensure_user_exists(user_id)

            with self.pooled_connection() as conn:
                conn.execute("BEGIN")

                try:
                    cursor = conn.execute(
                        """
                        SELECT * FROM archived_tasks
                        WHERE user_id = ? AND (struck_today = 1 OR struck_forever = 1)
                        ORDER BY created_at DESC
                    """,
                        (user_id,),
                    )

                    rows = cursor.fetchall()

                    tasks = []
                    for row in rows:
                        try:
                            task_dict = self._row_to_task_dict(row)
                            if self._validate_task(task_dict):
                                tasks.append(task_dict)
                            else:
                                self.logger.warning(
                                    "Invalid archived task data found for user %s, skipping corrupted task",
                                    user_id,
                                )
                        except Exception as row_e:
                            self.logger.warning(
                                "Failed to convert archived task row for user %s: %s",
                                user_id,
                                row_e,
                            )
                            continue

                    conn.commit()
                    self.logger.info(
                        "Successfully loaded %d struck archived tasks for user %s",
                        len(tasks),
                        user_id,
                    )
                    return tasks
                except Exception as inner_e:
                    try:
                        conn.rollback()
                    except Exception:
                        self.logger.exception("Rollback failed for user %s", user_id)
                    self.logger.exception("Transaction failed for user %s", user_id)
                    raise

        except Exception as e:
            self.logger.exception("Error loading struck archived tasks for user %s", user_id)
            raise DatabaseError(
                message=f"Error loading struck archived tasks for user {user_id}",
                cause=e,
            )

    def get_archived_task_count(self, user_id: str) -> int:
        """Get the count of archived tasks for a user.

        Useful for pagination and UI display.
        """
        try:
            self._ensure_user_exists(user_id)

            with self.pooled_connection() as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM archived_tasks WHERE user_id = ?",
                    (user_id,),
                )
                count = cursor.fetchone()[0]
                self.logger.info(f"User {user_id} has {count} archived tasks")
                return count

        except Exception as e:
            self.logger.exception(
                f"Error getting archived task count for user {user_id}"
            )
            raise DatabaseError(
                message=f"Error getting archived task count for user {user_id}",
                cause=e,
            )

    def auto_archive_old_completed_tasks(self, user_id: str, days_old: int = 40) -> int:
        """Automatically archive completed tasks older than specified days.

        This is typically called by a background job. Returns the number of tasks archived.
        Only archives tasks that are:
        - Completed (completed=True)
        - Have a completed_at timestamp older than days_old days
        - Are still in the tasks table (not already archived)
        """
        try:
            self._ensure_user_exists(user_id)

            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")

                try:
                    # Calculate cutoff date
                    cutoff_date = datetime.now() - timedelta(days=days_old)
                    cutoff_iso = cutoff_date.isoformat()

                    # Find completed tasks older than cutoff
                    cursor = conn.execute(
                        """
                        SELECT id FROM tasks
                        WHERE user_id = ? AND completed = 1 AND completed_at < ?
                    """,
                        (user_id, cutoff_iso),
                    )

                    task_ids = [row["id"] for row in cursor.fetchall()]
                    archived_count = 0

                    # Archive each task
                    for task_id in task_ids:
                        try:
                            # Get the task
                            task_cursor = conn.execute(
                                "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
                                (task_id, user_id),
                            )
                            task_row = task_cursor.fetchone()

                            if not task_row:
                                continue

                            # Convert to dict and prepare archive row
                            task_dict = self._row_to_task_dict(task_row)

                            archive_row = (
                                task_dict["id"],
                                user_id,
                                task_dict.get("title", ""),
                                task_dict.get("description", ""),
                                task_dict.get("project", ""),
                                task_dict.get("owner", ""),
                                task_dict.get("priority", "medium"),
                                task_dict.get("status", "pending"),
                                task_dict.get("completed", False),
                                task_dict.get("completed_at"),
                                task_dict.get("due_date"),
                                task_dict.get("estimated_duration", 60),
                                task_dict.get("scheduled_hour"),
                                task_dict.get("scheduled_minute"),
                                task_dict.get("scheduled_date"),
                                task_dict.get("scheduled_duration"),
                                task_dict.get("struck_forever", False),
                                task_dict.get("struck_today", False),
                                task_dict.get("struck_date"),
                                task_dict.get("strike_report"),
                                task_dict.get("strike_count", 0),
                                json.dumps(task_dict.get("daily_strikes", {})),
                                task_dict.get("refreshed_at"),
                                task_dict.get("recurrence_type") or None,
                                task_dict.get("recurrence_param"),
                                task_dict.get("snoozed_until"),
                                json.dumps(task_dict.get("subtasks") or []),
                                task_dict.get("parent_id"),
                                task_dict.get("created_at", datetime.now().isoformat()),
                                task_dict.get("updated_at", datetime.now().isoformat()),
                                datetime.now().isoformat(),  # archived_at
                            )

                            # Insert into archived_tasks
                            conn.execute(
                                """
                                INSERT INTO archived_tasks (
                                    id, user_id, title, description, project, owner, priority, status,
                                    completed, completed_at, due_date, estimated_duration, scheduled_hour,
                                    scheduled_minute, scheduled_date, scheduled_duration, struck_forever, struck_today, struck_date, strike_report, strike_count,
                                    daily_strikes, refreshed_at, recurrence_type, recurrence_param, snoozed_until, subtasks, parent_id, created_at, updated_at, archived_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                                archive_row,
                            )

                            # Delete from tasks
                            conn.execute(
                                "DELETE FROM tasks WHERE id = ? AND user_id = ?",
                                (task_id, user_id),
                            )

                            archived_count += 1

                        except Exception as task_e:
                            self.logger.warning(
                                f"Failed to auto-archive task {task_id} for user {user_id}: {task_e}"
                            )
                            continue

                    conn.commit()
                    self.logger.info(
                        f"Auto-archived {archived_count} old completed tasks for user {user_id} (>{days_old} days old)"
                    )
                    return archived_count

                except Exception as inner_e:
                    conn.rollback()
                    self.logger.error(
                        f"Transaction failed during auto-archive for user {user_id}: {inner_e}"
                    )
                    raise

        except Exception as e:
            self.logger.exception(f"Error auto-archiving old tasks for user {user_id}")
            raise DatabaseError(
                message=f"Error auto-archiving old tasks for user {user_id}",
                cause=e,
            )

    # Settings Management Methods
    def load_settings_for_user(self, user_id: str) -> Dict[str, Any]:
        """Load settings for a specific user from database with comprehensive isolation"""
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            try:
                with self._lock:
                    # Validate user_id
                    if (
                        not user_id
                        or not isinstance(user_id, str)
                        or len(user_id.strip()) == 0
                    ):
                        self.logger.error("Invalid user_id provided: %s", user_id)
                        raise ValidationError(message="Invalid user_id")

                    # Ensure user exists
                    self._ensure_user_exists(user_id)

                    with self._get_connection() as conn:
                        # Start read-only transaction (deferred)
                        conn.execute("BEGIN")

                        try:
                            # Check if user preferences table exists (newer migration)
                            cursor = conn.execute(
                                "SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'"
                            )
                            if cursor.fetchone():
                                col_cursor = conn.execute(
                                    "PRAGMA table_info(user_preferences)"
                                )
                                cols = [row[1] for row in col_cursor.fetchall()]
                                has_qp_column = "quick_project_from_title" in cols
                                has_casual_column = "casual_dates" in cols
                                has_last_reset_column = "last_daily_reset_at" in cols
                                has_mini_analytics_column = (
                                    "mini_analytics_interval" in cols
                                )
                                has_settings_layout = "settings_layout" in cols
                                has_streak_skip_weekends = (
                                    "streak_skip_weekends" in cols
                                )
                                has_streak_count_new_tasks = (
                                    "streak_count_new_tasks" in cols
                                )
                                has_streak_count_settings = (
                                    "streak_count_settings" in cols
                                )
                                has_finish = "finish" in cols
                                has_intensity = "intensity" in cols
                                has_perf_disable_blur = "perf_disable_blur" in cols
                                has_perf_disable_shadows = (
                                    "perf_disable_shadows" in cols
                                )
                                has_perf_disable_animations = (
                                    "perf_disable_animations" in cols
                                )
                                has_perf_disable_glow = "perf_disable_glow" in cols
                                has_compact_mode = "compact_mode" in cols

                                select_cols = [
                                    "theme",
                                    "dpi_scale",
                                    "autosave_interval",
                                    "notifications",
                                    "daily_reset_time",
                                ]
                                if has_last_reset_column:
                                    select_cols.append("last_daily_reset_at")
                                select_cols.extend(["timezone", "language"])
                                if has_mini_analytics_column:
                                    select_cols.append("mini_analytics_interval")
                                if has_settings_layout:
                                    select_cols.append("settings_layout")
                                if has_qp_column:
                                    select_cols.append("quick_project_from_title")
                                if has_casual_column:
                                    select_cols.append("casual_dates")
                                if has_streak_skip_weekends:
                                    select_cols.append("streak_skip_weekends")
                                if has_streak_count_new_tasks:
                                    select_cols.append("streak_count_new_tasks")
                                if has_streak_count_settings:
                                    select_cols.append("streak_count_settings")
                                if has_finish:
                                    select_cols.append("finish")
                                if has_intensity:
                                    select_cols.append("intensity")
                                if has_perf_disable_blur:
                                    select_cols.append("perf_disable_blur")
                                if has_perf_disable_shadows:
                                    select_cols.append("perf_disable_shadows")
                                if has_perf_disable_animations:
                                    select_cols.append("perf_disable_animations")

                                cursor = conn.execute(
                                    f"SELECT {', '.join(select_cols)} FROM user_preferences WHERE user_id = ?",
                                    (user_id,),
                                )

                                result = cursor.fetchone()
                                if result:
                                    raw = dict(zip(select_cols, result))
                                    settings = {
                                        "theme": raw.get("theme") or "orange",
                                        "dpi_scale": raw.get("dpi_scale") or 100,
                                        "autosave_interval": raw.get(
                                            "autosave_interval"
                                        )
                                        or 30,
                                        "notifications": bool(raw.get("notifications"))
                                        if raw.get("notifications") is not None
                                        else True,
                                        "daily_reset_time": raw.get("daily_reset_time")
                                        or "06:00",
                                        "last_daily_reset_at": raw.get(
                                            "last_daily_reset_at"
                                        ),
                                        "timezone": raw.get("timezone") or "UTC",
                                        "language": raw.get("language") or "en",
                                        "mini_analytics_interval": raw.get(
                                            "mini_analytics_interval"
                                        )
                                        if raw.get("mini_analytics_interval")
                                        is not None
                                        else 5,
                                        "settings_layout": raw.get("settings_layout")
                                        or "scroll",
                                        "quick_project_from_title": bool(
                                            raw.get("quick_project_from_title")
                                        )
                                        if raw.get("quick_project_from_title")
                                        is not None
                                        else False,
                                        "casual_dates": bool(raw.get("casual_dates"))
                                        if raw.get("casual_dates") is not None
                                        else False,
                                        "streak_skip_weekends": bool(
                                            raw.get("streak_skip_weekends")
                                        )
                                        if raw.get("streak_skip_weekends") is not None
                                        else False,
                                        "streak_count_new_tasks": bool(
                                            raw.get("streak_count_new_tasks")
                                        )
                                        if raw.get("streak_count_new_tasks") is not None
                                        else False,
                                        "streak_count_settings": bool(
                                            raw.get("streak_count_settings")
                                        )
                                        if raw.get("streak_count_settings") is not None
                                        else False,
                                        "finish": raw.get("finish") or "glossy",
                                        "intensity": raw.get("intensity") or "5",
                                        "perf_disable_blur": bool(
                                            raw.get("perf_disable_blur")
                                        )
                                        if "perf_disable_blur" in raw
                                        and raw.get("perf_disable_blur") is not None
                                        else False,
                                        "perf_disable_shadows": bool(
                                            raw.get("perf_disable_shadows")
                                        )
                                        if "perf_disable_shadows" in raw
                                        and raw.get("perf_disable_shadows") is not None
                                        else False,
                                        "perf_disable_animations": bool(
                                            raw.get("perf_disable_animations")
                                        )
                                        if "perf_disable_animations" in raw
                                        and raw.get("perf_disable_animations")
                                        is not None
                                        else False,
                                        "perf_disable_glow": bool(
                                            raw.get("perf_disable_glow")
                                        )
                                        if "perf_disable_glow" in raw
                                        and raw.get("perf_disable_glow") is not None
                                        else False,
                                        "created_at": raw.get("created_at"),
                                        "updated_at": raw.get("updated_at"),
                                    }

                                    validated_settings = self._validate_settings(
                                        settings
                                    )
                                    conn.commit()
                                    self.logger.info(
                                        f"Successfully loaded settings for user {user_id}"
                                    )
                                    return validated_settings
                            else:
                                # Fallback to old settings table
                                col_cursor = conn.execute("PRAGMA table_info(settings)")
                                cols = [row[1] for row in col_cursor.fetchall()]
                                has_last_reset_column = "last_daily_reset_at" in cols
                                has_mini_analytics_column = (
                                    "mini_analytics_interval" in cols
                                )
                                has_settings_layout = "settings_layout" in cols

                                select_cols = [
                                    "theme",
                                    "dpi_scale",
                                    "autosave_interval",
                                    "notifications",
                                    "daily_reset_time",
                                ]
                                if has_last_reset_column:
                                    select_cols.append("last_daily_reset_at")
                                if has_mini_analytics_column:
                                    select_cols.append("mini_analytics_interval")
                                if has_settings_layout:
                                    select_cols.append("settings_layout")
                                cursor = conn.execute(
                                    f"SELECT {', '.join(select_cols)} FROM settings WHERE user_id = ?",
                                    (user_id,),
                                )
                                result = cursor.fetchone()

                                if result:
                                    raw = dict(zip(select_cols, result))
                                    settings = {
                                        "theme": raw.get("theme") or "orange",
                                        "dpi_scale": raw.get("dpi_scale") or 100,
                                        "autosave_interval": raw.get(
                                            "autosave_interval"
                                        )
                                        or 30,
                                        "notifications": bool(raw.get("notifications"))
                                        if raw.get("notifications") is not None
                                        else True,
                                        "daily_reset_time": raw.get("daily_reset_time")
                                        or "06:00",
                                        "last_daily_reset_at": raw.get(
                                            "last_daily_reset_at"
                                        )
                                        if has_last_reset_column
                                        else None,
                                        "mini_analytics_interval": raw.get(
                                            "mini_analytics_interval"
                                        )
                                        if has_mini_analytics_column
                                        and raw.get("mini_analytics_interval")
                                        is not None
                                        else 5,
                                        "settings_layout": raw.get("settings_layout")
                                        or "scroll",
                                        "timezone": "UTC",  # Default for old data
                                        "language": "en",  # Default for old data
                                    }

                                    validated_settings = self._validate_settings(
                                        settings
                                    )
                                    conn.commit()
                                    self.logger.info(
                                        f"Successfully loaded settings for user {user_id} (legacy)"
                                    )
                                    return validated_settings

                            # No settings found, create default
                            default_settings = self._get_default_settings()
                            self._create_default_settings_for_user(
                                conn, user_id, default_settings
                            )
                            conn.commit()
                            self.logger.info(
                                f"Created default settings for user {user_id}"
                            )
                            return default_settings

                        except Exception as inner_e:
                            try:
                                conn.rollback()
                            except Exception:  # noqa: broad-except - Data layer defensive exception handling
                                self.logger.exception(
                                    "Rollback failed for user %s", user_id
                                )
                            self.logger.exception(
                                "Transaction failed for user %s, attempt %d",
                                user_id,
                                attempt + 1,
                            )
                            raise

            except Exception as e:
                self.logger.exception(
                    "Error loading settings for user %s, attempt %d",
                    user_id,
                    attempt + 1,
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2**attempt))  # Exponential backoff
                    continue

                raise DatabaseError(
                    message=f"Error loading settings for user {user_id}",
                    cause=e,
                )

        raise DatabaseError(message=f"Error loading settings for user {user_id}")

    def _get_default_settings(self) -> Dict[str, Any]:
        """Get default settings with validation"""
        return {
            "theme": "orange",
            "dpi_scale": 100,
            "autosave_interval": 30,
            "notifications": True,
            "daily_reset_time": "06:00",
            "last_daily_reset_at": None,
            "timezone": "UTC",
            "language": "en",
            "mini_analytics_interval": 5,
            "settings_layout": "scroll",
            # Feature flag: when true, first word before the first comma in a new task
            # title becomes the project name. Defaults to False for backwards compatibility.
            "quick_project_from_title": False,
            # When true, show human-friendly relative dates ("today", "in 2 days", "this weekend").
            "casual_dates": False,
            # Compact layout flag for tighter UI (5.20). Off by default for backwards
            # compatibility.
            "compact_mode": False,
            # Default task duration in minutes (5-480)
            "default_task_duration": 60,
            # Start page on app launch
            "start_page": "tasks",
            # Play notification sounds
            "notification_sound": False,
            # Week start day (0=Sunday, 1=Monday)
            "week_start_day": 1,
            # Performance-related UI flags (Chrome / low FPS helpers)
            "perf_disable_blur": False,
            "perf_disable_shadows": False,
            "perf_disable_animations": False,
            "perf_disable_glow": False,
        }

    def _validate_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize settings data"""
        validated = {}

        # Theme validation - include all valid theme values from frontend
        theme = settings.get("theme", "orange")
        # Note: this list must stay in sync with frontend theme selector and CSS
        valid_themes = [
            "orange",
            "blue",
            "green",
            "purple",
            "dark",
            "light",
            "self-esteem",
            "anxiety",
            "depression",
            "focus",
            "yellow",
            "speedy",
            "auto",
        ]
        if not isinstance(theme, str) or theme not in valid_themes:
            theme = "orange"
        validated["theme"] = theme

        # DPI scale validation
        dpi_scale = settings.get("dpi_scale", 100)
        if not isinstance(dpi_scale, int) or dpi_scale < 50 or dpi_scale > 200:
            dpi_scale = 100
        validated["dpi_scale"] = dpi_scale

        # Autosave interval validation
        autosave_interval = settings.get("autosave_interval", 30)
        if (
            not isinstance(autosave_interval, int)
            or autosave_interval < 5
            or autosave_interval > 300
        ):
            autosave_interval = 30
        validated["autosave_interval"] = autosave_interval

        # Notifications validation
        notifications = settings.get("notifications", True)
        if not isinstance(notifications, bool):
            notifications = True
        validated["notifications"] = notifications

        # Daily reset time validation
        daily_reset_time = settings.get("daily_reset_time", "06:00")
        if not isinstance(daily_reset_time, str) or not self._validate_time_format(
            daily_reset_time
        ):
            daily_reset_time = "06:00"
        validated["daily_reset_time"] = daily_reset_time

        last_daily_reset_at = settings.get("last_daily_reset_at")
        if last_daily_reset_at is None:
            validated["last_daily_reset_at"] = None
        elif isinstance(last_daily_reset_at, str):
            try:
                datetime.fromisoformat(last_daily_reset_at.replace("Z", "+00:00"))
                validated["last_daily_reset_at"] = last_daily_reset_at
            except Exception:  # noqa: broad-except - Data layer defensive exception handling
                validated["last_daily_reset_at"] = None
        else:
            validated["last_daily_reset_at"] = None

        # Timezone validation
        timezone = settings.get("timezone", "UTC")
        if not isinstance(timezone, str) or len(timezone) > 50:
            timezone = "UTC"
        validated["timezone"] = timezone

        # Language validation
        language = settings.get("language", "en")
        if not isinstance(language, str) or len(language) > 10:
            language = "en"
        validated["language"] = language

        # Mini analytics rotation interval validation
        mai = settings.get("mini_analytics_interval", 5)
        try:
            mai = int(mai)
        except Exception:  # noqa: broad-except - Data layer defensive exception handling
            mai = 5
        if mai not in [0, 5, 10, 20, 30, 60]:
            mai = 5
        validated["mini_analytics_interval"] = mai

        layout = settings.get("settings_layout", "scroll")
        if not isinstance(layout, str) or layout not in ["scroll", "tabs"]:
            layout = "scroll"
        validated["settings_layout"] = layout

        # Quick project-from-title flag
        qp = settings.get("quick_project_from_title", False)
        if not isinstance(qp, bool):
            qp = False
        validated["quick_project_from_title"] = qp

        # Casual dates flag
        casual = settings.get("casual_dates", False)
        if not isinstance(casual, bool):
            casual = False
        validated["casual_dates"] = casual

        # Compact mode flag
        compact_mode = settings.get("compact_mode", False)
        if not isinstance(compact_mode, bool):
            compact_mode = False
        validated["compact_mode"] = compact_mode

        # Default task duration (minutes)
        dtd = settings.get("default_task_duration", 60)
        try:
            dtd = int(dtd)
        except Exception:  # noqa: broad-except
            dtd = 60
        if dtd < 5 or dtd > 480:
            dtd = 60
        validated["default_task_duration"] = dtd

        # Start page
        sp = settings.get("start_page", "tasks")
        if not isinstance(sp, str) or sp not in (
            "tasks",
            "planner",
            "notes",
            "analytics",
        ):
            sp = "tasks"
        validated["start_page"] = sp

        # Notification sound
        ns = settings.get("notification_sound", False)
        if not isinstance(ns, bool):
            ns = False
        validated["notification_sound"] = ns

        # Week start day (0=Sunday, 1=Monday)
        wsd = settings.get("week_start_day", 1)
        try:
            wsd = int(wsd)
        except Exception:  # noqa: broad-except
            wsd = 1
        if wsd not in (0, 1):
            wsd = 1
        validated["week_start_day"] = wsd

        # Streak settings flags
        streak_skip_weekends = settings.get("streak_skip_weekends", False)
        if not isinstance(streak_skip_weekends, bool):
            streak_skip_weekends = False
        validated["streak_skip_weekends"] = streak_skip_weekends

        streak_count_new_tasks = settings.get("streak_count_new_tasks", False)
        if not isinstance(streak_count_new_tasks, bool):
            streak_count_new_tasks = False
        validated["streak_count_new_tasks"] = streak_count_new_tasks

        streak_count_settings = settings.get("streak_count_settings", False)
        if not isinstance(streak_count_settings, bool):
            streak_count_settings = False
        validated["streak_count_settings"] = streak_count_settings

        # Finish setting (glossy/matte)
        finish = settings.get("finish", "glossy")
        if not isinstance(finish, str) or finish not in ["glossy", "matte"]:
            finish = "glossy"
        validated["finish"] = finish

        # Intensity setting (1-10)
        intensity = settings.get("intensity", "5")
        if not isinstance(intensity, str) or intensity not in [
            "1",
            "2",
            "3",
            "4",
            "5",
            "6",
            "7",
            "8",
            "9",
            "10",
        ]:
            intensity = "5"
        validated["intensity"] = intensity

        # Performance flags (Chrome / low FPS helpers)
        perf_disable_blur = settings.get("perf_disable_blur", False)
        if not isinstance(perf_disable_blur, bool):
            perf_disable_blur = False
        validated["perf_disable_blur"] = perf_disable_blur

        perf_disable_shadows = settings.get("perf_disable_shadows", False)
        if not isinstance(perf_disable_shadows, bool):
            perf_disable_shadows = False
        validated["perf_disable_shadows"] = perf_disable_shadows

        perf_disable_animations = settings.get("perf_disable_animations", False)
        if not isinstance(perf_disable_animations, bool):
            perf_disable_animations = False
        validated["perf_disable_animations"] = perf_disable_animations

        perf_disable_glow = settings.get("perf_disable_glow", False)
        if not isinstance(perf_disable_glow, bool):
            perf_disable_glow = False
        validated["perf_disable_glow"] = perf_disable_glow

        return validated

    def _validate_time_format(self, time_str: str) -> bool:
        """Validate time format (HH:MM)"""
        try:
            if not isinstance(time_str, str):
                return False
            parts = time_str.split(":")
            if len(parts) != 2:
                return False
            hour, minute = int(parts[0]), int(parts[1])
            return 0 <= hour <= 23 and 0 <= minute <= 59
        except (ValueError, IndexError):
            return False

    def _create_default_settings_for_user(
        self, conn, user_id: str, settings: Dict[str, Any]
    ):
        """Create default settings for a user"""
        try:
            # Try to insert into user_preferences table first (newer schema).
            # If quick_project_from_title column exists it will default to 0/False
            # for freshly created rows unless migrations added an explicit default.
            conn.execute(
                """
                INSERT OR IGNORE INTO user_preferences
                (user_id, theme, dpi_scale, autosave_interval, notifications,
                 daily_reset_time, timezone, language)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    user_id,
                    settings["theme"],
                    settings["dpi_scale"],
                    settings["autosave_interval"],
                    settings["notifications"],
                    settings["daily_reset_time"],
                    settings["timezone"],
                    settings["language"],
                ),
            )
        except sqlite3.OperationalError:
            # Fallback to old settings table
            conn.execute(
                """
                INSERT OR IGNORE INTO settings
                (user_id, theme, dpi_scale, autosave_interval, notifications, daily_reset_time)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    user_id,
                    settings["theme"],
                    settings["dpi_scale"],
                    settings["autosave_interval"],
                    settings["notifications"],
                    settings["daily_reset_time"],
                ),
            )

    def save_settings_for_user(self, user_id: str, settings: Dict[str, Any]) -> bool:
        """Save settings for a specific user to database with comprehensive validation and isolation"""
        max_retries = 3
        retry_delay = 0.1

        for attempt in range(max_retries):
            with self._lock:
                try:
                    # Validate user_id
                    if (
                        not user_id
                        or not isinstance(user_id, str)
                        or len(user_id.strip()) == 0
                    ):
                        self.logger.error(f"Invalid user_id provided: {user_id}")
                        return False

                    # Validate and sanitize settings
                    validated_settings = self._validate_settings(settings)

                    # Ensure user exists
                    self._ensure_user_exists(user_id)

                    with self._get_connection() as conn:
                        # Start transaction
                        conn.execute("BEGIN IMMEDIATE TRANSACTION")

                        try:
                            # Check if user preferences table exists (newer migration)
                            cursor = conn.execute(
                                "SELECT name FROM sqlite_master WHERE type='table' AND name='user_preferences'"
                            )
                            table_exists = cursor.fetchone() is not None

                            if table_exists:
                                # Ensure settings-related columns exist (schema may be from older builds)
                                try:
                                    col_cursor = conn.execute(
                                        "PRAGMA table_info(user_preferences)"
                                    )
                                    cols = [row[1] for row in col_cursor.fetchall()]
                                    if "quick_project_from_title" not in cols:
                                        conn.execute(
                                            "ALTER TABLE user_preferences ADD COLUMN quick_project_from_title INTEGER DEFAULT 0"
                                        )
                                    if "casual_dates" not in cols:
                                        conn.execute(
                                            "ALTER TABLE user_preferences ADD COLUMN casual_dates INTEGER DEFAULT 0"
                                        )
                                    if "last_daily_reset_at" not in cols:
                                        conn.execute(
                                            "ALTER TABLE user_preferences ADD COLUMN last_daily_reset_at TEXT"
                                        )
                                    if "mini_analytics_interval" not in cols:
                                        conn.execute(
                                            "ALTER TABLE user_preferences ADD COLUMN mini_analytics_interval INTEGER DEFAULT 5"
                                        )
                                    if "settings_layout" not in cols:
                                        conn.execute(
                                            "ALTER TABLE user_preferences ADD COLUMN settings_layout TEXT DEFAULT 'scroll'"
                                        )
                                    if "streak_skip_weekends" not in cols:
                                        conn.execute(
                                            "ALTER TABLE user_preferences ADD COLUMN streak_skip_weekends INTEGER DEFAULT 0"
                                        )
                                    if "streak_count_new_tasks" not in cols:
                                        conn.execute(
                                            "ALTER TABLE user_preferences ADD COLUMN streak_count_new_tasks INTEGER DEFAULT 0"
                                        )
                                    if "streak_count_settings" not in cols:
                                        conn.execute(
                                            "ALTER TABLE user_preferences ADD COLUMN streak_count_settings INTEGER DEFAULT 0"
                                        )
                                    if "finish" not in cols:
                                        conn.execute(
                                            "ALTER TABLE user_preferences ADD COLUMN finish TEXT DEFAULT 'glossy'"
                                        )
                                    if "intensity" not in cols:
                                        conn.execute(
                                            "ALTER TABLE user_preferences ADD COLUMN intensity TEXT DEFAULT '5'"
                                        )
                                    if "perf_disable_blur" not in cols:
                                        conn.execute(
                                            "ALTER TABLE user_preferences ADD COLUMN perf_disable_blur INTEGER DEFAULT 0"
                                        )
                                    if "perf_disable_shadows" not in cols:
                                        conn.execute(
                                            "ALTER TABLE user_preferences ADD COLUMN perf_disable_shadows INTEGER DEFAULT 0"
                                        )
                                    if "perf_disable_animations" not in cols:
                                        conn.execute(
                                            "ALTER TABLE user_preferences ADD COLUMN perf_disable_animations INTEGER DEFAULT 0"
                                        )
                                    if "perf_disable_glow" not in cols:
                                        conn.execute(
                                            "ALTER TABLE user_preferences ADD COLUMN perf_disable_glow INTEGER DEFAULT 0"
                                        )
                                    if "compact_mode" not in cols:
                                        conn.execute(
                                            "ALTER TABLE user_preferences ADD COLUMN compact_mode INTEGER DEFAULT 0"
                                        )
                                except Exception as schema_e:
                                    # Log but do not fail save if ALTER fails; feature will just fall back to default
                                    self.logger.warning(
                                        f"Could not ensure settings columns on user_preferences: {schema_e}"
                                    )

                                # Use new user_preferences table (including additional flags when available)
                                conn.execute(
                                    """
                                    INSERT OR REPLACE INTO user_preferences (
                                        user_id, theme, dpi_scale, autosave_interval, notifications,
                                        daily_reset_time, last_daily_reset_at, timezone, language, mini_analytics_interval,
                                        settings_layout,
                                        quick_project_from_title, casual_dates,
                                        streak_skip_weekends, streak_count_new_tasks, streak_count_settings,
                                        finish, intensity,
                                        perf_disable_blur, perf_disable_shadows, perf_disable_animations, perf_disable_glow,
                                        compact_mode,
                                        updated_at
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                    (
                                        user_id,
                                        validated_settings["theme"],
                                        validated_settings["dpi_scale"],
                                        validated_settings["autosave_interval"],
                                        validated_settings["notifications"],
                                        validated_settings["daily_reset_time"],
                                        validated_settings.get("last_daily_reset_at"),
                                        validated_settings["timezone"],
                                        validated_settings["language"],
                                        validated_settings.get(
                                            "mini_analytics_interval", 5
                                        ),
                                        validated_settings.get(
                                            "settings_layout", "scroll"
                                        ),
                                        1
                                        if validated_settings.get(
                                            "quick_project_from_title", False
                                        )
                                        else 0,
                                        1
                                        if validated_settings.get("casual_dates", False)
                                        else 0,
                                        1
                                        if validated_settings.get(
                                            "streak_skip_weekends", False
                                        )
                                        else 0,
                                        1
                                        if validated_settings.get(
                                            "streak_count_new_tasks", False
                                        )
                                        else 0,
                                        1
                                        if validated_settings.get(
                                            "streak_count_settings", False
                                        )
                                        else 0,
                                        validated_settings.get("finish", "glossy"),
                                        validated_settings.get("intensity", "5"),
                                        1
                                        if validated_settings.get(
                                            "perf_disable_blur", False
                                        )
                                        else 0,
                                        1
                                        if validated_settings.get(
                                            "perf_disable_shadows", False
                                        )
                                        else 0,
                                        1
                                        if validated_settings.get(
                                            "perf_disable_animations", False
                                        )
                                        else 0,
                                        1
                                        if validated_settings.get(
                                            "perf_disable_glow", False
                                        )
                                        else 0,
                                        1
                                        if validated_settings.get("compact_mode", False)
                                        else 0,
                                        datetime.now().isoformat(),
                                    ),
                                )
                            else:
                                # Fallback to old settings table
                                try:
                                    col_cursor = conn.execute(
                                        "PRAGMA table_info(settings)"
                                    )
                                    cols = [row[1] for row in col_cursor.fetchall()]
                                    if "mini_analytics_interval" not in cols:
                                        conn.execute(
                                            "ALTER TABLE settings ADD COLUMN mini_analytics_interval INTEGER DEFAULT 5"
                                        )
                                    if "settings_layout" not in cols:
                                        conn.execute(
                                            "ALTER TABLE settings ADD COLUMN settings_layout TEXT DEFAULT 'scroll'"
                                        )
                                except Exception as schema_e:
                                    self.logger.exception(
                                        "Could not ensure settings columns on settings table"
                                    )
                                    raise schema_e
                                conn.execute(
                                    """
                                    INSERT OR REPLACE INTO settings (
                                        user_id, theme, dpi_scale, autosave_interval, notifications,
                                        daily_reset_time, last_daily_reset_at, mini_analytics_interval, settings_layout, updated_at
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                    (
                                        user_id,
                                        validated_settings["theme"],
                                        validated_settings["dpi_scale"],
                                        validated_settings["autosave_interval"],
                                        validated_settings["notifications"],
                                        validated_settings["daily_reset_time"],
                                        validated_settings.get("last_daily_reset_at"),
                                        validated_settings.get(
                                            "mini_analytics_interval", 5
                                        ),
                                        validated_settings.get(
                                            "settings_layout", "scroll"
                                        ),
                                        datetime.now().isoformat(),
                                    ),
                                )

                            # Commit the transaction
                            conn.commit()
                            self.logger.info(
                                f"Successfully saved settings for user {user_id}"
                            )
                            return True

                        except Exception as inner_e:
                            conn.rollback()
                            self.logger.error(
                                f"Transaction failed for user {user_id}, attempt {attempt + 1}: {inner_e}"
                            )
                            raise inner_e

                except Exception as e:
                    self.logger.error(
                        f"Error saving settings for user {user_id}, attempt {attempt + 1}: {e}"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay * (2**attempt))  # Exponential backoff
                        continue
                    else:
                        return False

        return False

    # Backward compatibility methods
    def load_tasks(self, user_id: str = None):
        """Load tasks with optional user_id - backward compatibility"""
        if user_id is None:
            user_id = DEFAULT_USER_ID
            self.logger.info(
                f"load_tasks called without user_id, using default: {user_id}"
            )
        else:
            self.logger.info(f"load_tasks called with user_id: {user_id}")

        return self.load_tasks_for_user(user_id)

    # Notes Management Methods
    def _row_to_note_dict(self, row) -> Dict[str, Any]:
        """Convert a notes row to a dict, tolerating missing columns."""
        keys = row.keys()
        return {
            "id": row["id"],
            "title": row["title"],
            "content": row["content"] or "",
            "folder": row["folder"] if "folder" in keys else None,
            "pinned": bool(row["pinned"]) if "pinned" in keys else False,
            "archived": bool(row["archived"]) if "archived" in keys else False,
            "deleted_at": row["deleted_at"] if "deleted_at" in keys else None,
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def load_notes_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Load non-trashed notes for a specific user from database."""
        try:
            self._ensure_user_exists(user_id)
            with self.pooled_connection() as conn:
                cursor = conn.execute(
                    """SELECT * FROM notes
                       WHERE user_id = ? AND (deleted_at IS NULL OR deleted_at = '')
                       ORDER BY updated_at DESC""",
                    (user_id,),
                )
                rows = cursor.fetchall()
                return [self._row_to_note_dict(row) for row in rows]
        except Exception as e:
            self.logger.exception("Error loading notes for user %s", user_id)
            raise DatabaseError(
                message=f"Error loading notes for user {user_id}", cause=e
            )

    def load_trashed_notes_for_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Load soft-deleted (trashed) notes for a user."""
        try:
            self._ensure_user_exists(user_id)
            with self.pooled_connection() as conn:
                cursor = conn.execute(
                    """SELECT * FROM notes
                       WHERE user_id = ? AND deleted_at IS NOT NULL AND deleted_at != ''
                       ORDER BY deleted_at DESC""",
                    (user_id,),
                )
                return [self._row_to_note_dict(row) for row in cursor.fetchall()]
        except Exception as e:
            self.logger.exception("Error loading trashed notes for user %s", user_id)
            raise DatabaseError(
                message=f"Error loading trashed notes for user {user_id}", cause=e
            )

    def create_note_for_user(
        self, user_id: str, note_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Create a single note for a user.

        Supports optional pinned/archived flags (5.2/5.26). These are stored as
        INTEGER 0/1 in SQLite but exposed as booleans in the returned dict.
        """
        try:
            self._ensure_user_exists(user_id)
            if "id" not in note_data:
                note_data["id"] = str(uuid.uuid4())
            title = (note_data.get("title") or "").strip() or "Untitled"
            content = note_data.get("content", "")
            folder_raw = note_data.get("folder")
            folder = (folder_raw or "").strip() if isinstance(folder_raw, str) else None
            if folder == "":
                folder = None
            pinned_flag = 1 if bool(note_data.get("pinned")) else 0
            archived_flag = 1 if bool(note_data.get("archived")) else 0
            now = datetime.now().isoformat()
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                try:
                    # Newer schema with pinned/archived columns.
                    conn.execute(
                        """INSERT INTO notes (id, user_id, title, content, folder, pinned, archived, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            note_data["id"],
                            user_id,
                            title,
                            content,
                            folder,
                            pinned_flag,
                            archived_flag,
                            now,
                            now,
                        ),
                    )
                except sqlite3.OperationalError:
                    # Backward-compatible fallback for older schemas without
                    # pinned/archived; flags will simply not be stored.
                    conn.execute(
                        """INSERT INTO notes (id, user_id, title, content, folder, created_at, updated_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (note_data["id"], user_id, title, content, folder, now, now),
                    )
                conn.commit()
            return {
                "id": note_data["id"],
                "title": title,
                "content": content,
                "folder": folder,
                "pinned": bool(pinned_flag),
                "archived": bool(archived_flag),
                "created_at": now,
                "updated_at": now,
            }
        except Exception as e:
            self.logger.error("Error creating note for user %s: %s", user_id, e)
            return None

    def update_note_for_user(
        self, user_id: str, note_id: str, note_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Update title/content/folder/pin/archive state of a note.

        Also snapshots the previous version into note_versions for history.
        """
        try:
            title = (note_data.get("title") or "").strip() or "Untitled"
            content = note_data.get("content", "")
            folder_raw = note_data.get("folder")
            folder = (folder_raw or "").strip() if isinstance(folder_raw, str) else None
            if folder == "":
                folder = None
            now = datetime.now().isoformat()
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                cursor = conn.execute(
                    "SELECT * FROM notes WHERE id = ? AND user_id = ?",
                    (note_id, user_id),
                )
                existing = cursor.fetchone()
                if not existing:
                    conn.rollback()
                    return None

                keys = existing.keys()
                current_pinned = existing["pinned"] if "pinned" in keys else 0
                current_archived = existing["archived"] if "archived" in keys else 0
                pinned_flag = (
                    1 if bool(note_data.get("pinned", bool(current_pinned))) else 0
                )
                archived_flag = (
                    1 if bool(note_data.get("archived", bool(current_archived))) else 0
                )

                # Snapshot previous version for history (best-effort)
                try:
                    old_content = existing["content"] or ""
                    old_title = existing["title"] or ""
                    if old_content.strip() or old_title.strip():
                        conn.execute(
                            """INSERT INTO note_versions (note_id, user_id, title, content, saved_at)
                               VALUES (?, ?, ?, ?, ?)""",
                            (note_id, user_id, old_title, old_content, now),
                        )
                        # Cap versions at 50 per note
                        conn.execute(
                            """DELETE FROM note_versions WHERE id IN (
                                SELECT id FROM note_versions
                                WHERE note_id = ? AND user_id = ?
                                ORDER BY saved_at DESC
                                LIMIT -1 OFFSET 50
                            )""",
                            (note_id, user_id),
                        )
                except Exception:  # noqa: broad-except
                    self.logger.exception(
                        "Failed to snapshot note version for note %s", note_id
                    )

                try:
                    conn.execute(
                        """UPDATE notes
                           SET title = ?, content = ?, folder = ?, pinned = ?, archived = ?, updated_at = ?
                           WHERE id = ? AND user_id = ?""",
                        (
                            title,
                            content,
                            folder,
                            pinned_flag,
                            archived_flag,
                            now,
                            note_id,
                            user_id,
                        ),
                    )
                except sqlite3.OperationalError:
                    # Fallback for schemas without pinned/archived.
                    conn.execute(
                        """UPDATE notes
                           SET title = ?, content = ?, folder = ?, updated_at = ?
                           WHERE id = ? AND user_id = ?""",
                        (title, content, folder, now, note_id, user_id),
                    )
                conn.commit()
            return {
                "id": note_id,
                "title": title,
                "content": content,
                "folder": folder,
                "pinned": bool(pinned_flag),
                "archived": bool(archived_flag),
                "updated_at": now,
            }
        except Exception as e:
            self.logger.error(
                "Error updating note %s for user %s: %s", note_id, user_id, e
            )
            return None

    def delete_note_for_user(self, user_id: str, note_id: str) -> bool:
        """Soft-delete a note (move to trash) by setting deleted_at."""
        try:
            now = datetime.now().isoformat()
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                try:
                    cursor = conn.execute(
                        """UPDATE notes SET deleted_at = ? WHERE id = ? AND user_id = ?
                           AND (deleted_at IS NULL OR deleted_at = '')""",
                        (now, note_id, user_id),
                    )
                    conn.commit()
                    return cursor.rowcount > 0
                except sqlite3.OperationalError:
                    # Fallback: schema may not have deleted_at yet; hard delete
                    conn.rollback()
                    conn.execute("BEGIN IMMEDIATE TRANSACTION")
                    cursor = conn.execute(
                        "DELETE FROM notes WHERE id = ? AND user_id = ?",
                        (note_id, user_id),
                    )
                    conn.commit()
                    return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(
                "Error soft-deleting note %s for user %s: %s", note_id, user_id, e
            )
            return False

    def restore_note_for_user(self, user_id: str, note_id: str) -> bool:
        """Restore a trashed note by clearing deleted_at."""
        try:
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                cursor = conn.execute(
                    """UPDATE notes SET deleted_at = NULL WHERE id = ? AND user_id = ?
                       AND deleted_at IS NOT NULL AND deleted_at != '' """,
                    (note_id, user_id),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(
                "Error restoring note %s for user %s: %s", note_id, user_id, e
            )
            return False

    def hard_delete_note_for_user(self, user_id: str, note_id: str) -> bool:
        """Permanently delete a note and its version history."""
        try:
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                try:
                    conn.execute(
                        "DELETE FROM note_versions WHERE note_id = ? AND user_id = ?",
                        (note_id, user_id),
                    )
                except sqlite3.OperationalError:
                    pass  # note_versions table may not exist on very old schemas
                cursor = conn.execute(
                    "DELETE FROM notes WHERE id = ? AND user_id = ?",
                    (note_id, user_id),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            self.logger.error(
                "Error hard-deleting note %s for user %s: %s", note_id, user_id, e
            )
            return False

    def load_note_versions(
        self, user_id: str, note_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Load version history for a note, newest first."""
        try:
            with self.pooled_connection() as conn:
                cursor = conn.execute(
                    """SELECT id, title, content, saved_at FROM note_versions
                       WHERE note_id = ? AND user_id = ?
                       ORDER BY saved_at DESC LIMIT ?""",
                    (note_id, user_id, int(limit)),
                )
                return [
                    {
                        "id": row["id"],
                        "title": row["title"] or "",
                        "content": row["content"] or "",
                        "saved_at": row["saved_at"],
                    }
                    for row in cursor.fetchall()
                ]
        except Exception as e:
            self.logger.exception("Error loading note versions for note %s", note_id)
            raise DatabaseError(message="Error loading note versions", cause=e)

    def restore_note_version(
        self, user_id: str, note_id: str, version_id: int
    ) -> Optional[Dict[str, Any]]:
        """Restore a note to a previous version. Returns updated note dict or None."""
        try:
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                ver_cur = conn.execute(
                    "SELECT title, content FROM note_versions WHERE id = ? AND note_id = ? AND user_id = ?",
                    (version_id, note_id, user_id),
                )
                ver_row = ver_cur.fetchone()
                if not ver_row:
                    conn.rollback()
                    return None

                # Snapshot current state before restoring
                cur_cur = conn.execute(
                    "SELECT title, content FROM notes WHERE id = ? AND user_id = ?",
                    (note_id, user_id),
                )
                cur_row = cur_cur.fetchone()
                now = datetime.now().isoformat()
                if cur_row:
                    conn.execute(
                        """INSERT INTO note_versions (note_id, user_id, title, content, saved_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (
                            note_id,
                            user_id,
                            cur_row["title"] or "",
                            cur_row["content"] or "",
                            now,
                        ),
                    )

                conn.execute(
                    """UPDATE notes SET title = ?, content = ?, updated_at = ?
                       WHERE id = ? AND user_id = ?""",
                    (ver_row["title"], ver_row["content"], now, note_id, user_id),
                )
                conn.commit()
            return {
                "id": note_id,
                "title": ver_row["title"] or "",
                "content": ver_row["content"] or "",
                "updated_at": now,
            }
        except Exception as e:
            self.logger.error(
                "Error restoring note version %s for note %s: %s",
                version_id,
                note_id,
                e,
            )
            return None

    def duplicate_note_for_user(
        self, user_id: str, note_id: str
    ) -> Optional[Dict[str, Any]]:
        """Duplicate an existing note with a new ID and '(Copy)' title suffix."""
        try:
            self._ensure_user_exists(user_id)
            with self.pooled_connection() as conn:
                cursor = conn.execute(
                    "SELECT * FROM notes WHERE id = ? AND user_id = ?",
                    (note_id, user_id),
                )
                row = cursor.fetchone()
                if not row:
                    return None

            keys = row.keys()
            original_title = row["title"] or "Untitled"
            new_title = original_title + " (Copy)"
            new_data = {
                "title": new_title,
                "content": row["content"] or "",
                "folder": row["folder"] if "folder" in keys else None,
                "pinned": False,
                "archived": False,
            }
            return self.create_note_for_user(user_id, new_data)
        except Exception as e:
            self.logger.error(
                "Error duplicating note %s for user %s: %s", note_id, user_id, e
            )
            return None

    def load_notes(self, user_id: str = None):
        """Backward-compatible wrapper for loading notes"""
        if user_id is None:
            user_id = DEFAULT_USER_ID
        return self.load_notes_for_user(user_id)

    def save_tasks(self, tasks, user_id: str = None):
        """Save tasks with optional user_id - backward compatibility"""
        if user_id is None:
            user_id = DEFAULT_USER_ID
            self.logger.info(
                f"save_tasks called without user_id, using default: {user_id}"
            )
        else:
            self.logger.info(f"save_tasks called with user_id: {user_id}")

        return self.save_tasks_for_user(user_id, tasks)

    def load_settings(self, user_id: str = None):
        """Load settings with optional user_id - backward compatibility"""
        if user_id is None:
            user_id = DEFAULT_USER_ID
        return self.load_settings_for_user(user_id)

    def save_settings(self, *args):
        """Save settings with flexible parameter handling - backward compatibility"""
        if len(args) == 1:
            # Called with one argument: save_settings(settings)
            settings = args[0]
            user_id = DEFAULT_USER_ID
        elif len(args) == 2:
            # Called with two arguments: save_settings(user_id, settings)
            user_id, settings = args
        else:
            raise TypeError("save_settings() takes 1 or 2 arguments")

        return self.save_settings_for_user(user_id, settings)

    # Mobile devices and inbox management methods
    def get_mobile_device_by_token_hash(
        self, user_id: str, token_hash: str
    ) -> Optional[Dict[str, Any]]:
        """Look up a mobile device for a user by token hash."""
        try:
            self._ensure_user_exists(user_id)
            with self._get_connection() as conn:
                conn.execute("BEGIN")
                cur = conn.execute(
                    """SELECT device_id, device_name, created_at, last_seen_at
                       FROM mobile_devices
                       WHERE user_id = ? AND token_hash = ?""",
                    (user_id, token_hash),
                )
                row = cur.fetchone()
                conn.commit()
            if not row:
                return None
            return {
                "device_id": row["device_id"],
                "device_name": row["device_name"],
                "created_at": row["created_at"],
                "last_seen_at": row["last_seen_at"],
            }
        except Exception as e:  # noqa: broad-except
            self.logger.exception("Error looking up mobile device for user %s", user_id)
            raise DatabaseError(
                message="Error looking up mobile device",
                details={"user_id": user_id},
                cause=e,
            )

    def save_mobile_device(
        self,
        user_id: str,
        device_id: str,
        device_name: str,
        token_hash: str,
        now_iso: str,
    ) -> None:
        """Insert or update a mobile device record and prune older devices."""
        try:
            self._ensure_user_exists(user_id)
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO mobile_devices (
                        user_id, device_id, device_name, token_hash, created_at, last_seen_at
                    ) VALUES (
                        ?, ?, ?, ?,
                        COALESCE((SELECT created_at FROM mobile_devices WHERE user_id = ? AND device_id = ?), ?),
                        ?
                    )
                    """,
                    (
                        user_id,
                        device_id,
                        device_name,
                        token_hash,
                        user_id,
                        device_id,
                        now_iso,
                        now_iso,
                    ),
                )
                # Enforce a maximum of 4 paired devices per user by deleting the oldest.
                try:
                    cur = conn.execute(
                        "SELECT device_id FROM mobile_devices WHERE user_id = ? ORDER BY created_at ASC",
                        (user_id,),
                    )
                    rows = cur.fetchall() or []
                    if len(rows) > 4:
                        to_delete = [
                            row["device_id"]
                            for row in rows[:-4]
                            if row and row["device_id"]
                        ]
                        if to_delete:
                            conn.executemany(
                                "DELETE FROM mobile_devices WHERE user_id = ? AND device_id = ?",
                                [(user_id, d) for d in to_delete],
                            )
                except Exception:  # noqa: broad-except
                    # Best-effort cleanup; do not fail pairing if pruning fails.
                    self.logger.exception(
                        "Failed to prune excess mobile devices for user %s", user_id
                    )
                conn.commit()
        except Exception as e:
            self.logger.exception("Error saving mobile device for user %s", user_id)
            raise DatabaseError(
                message="Error saving mobile device",
                details={"user_id": user_id},
                cause=e,
            )

    def list_mobile_devices(self, user_id: str) -> List[Dict[str, Any]]:
        """List all paired devices for a user."""
        try:
            self._ensure_user_exists(user_id)
            with self._get_connection() as conn:
                conn.execute("BEGIN")
                cur = conn.execute(
                    """SELECT device_id, device_name, created_at, last_seen_at
                       FROM mobile_devices
                       WHERE user_id = ?
                       ORDER BY last_seen_at DESC""",
                    (user_id,),
                )
                rows = cur.fetchall() or []
                conn.commit()
            devices: List[Dict[str, Any]] = []
            for row in rows:
                devices.append(
                    {
                        "device_id": row["device_id"],
                        "device_name": row["device_name"],
                        "created_at": row["created_at"],
                        "last_seen_at": row["last_seen_at"],
                    }
                )
            return devices
        except Exception as e:
            self.logger.exception("Error listing mobile devices for user %s", user_id)
            raise DatabaseError(
                message="Error listing mobile devices",
                details={"user_id": user_id},
                cause=e,
            )

    def delete_mobile_device(self, user_id: str, device_id: str) -> bool:
        """Unpair a mobile device for a user."""
        try:
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                cur = conn.execute(
                    "DELETE FROM mobile_devices WHERE user_id = ? AND device_id = ?",
                    (user_id, device_id),
                )
                conn.commit()
            return cur.rowcount > 0
        except Exception as e:
            self.logger.exception(
                "Error deleting mobile device %s for user %s", device_id, user_id
            )
            raise DatabaseError(
                message="Error deleting mobile device",
                details={"user_id": user_id, "device_id": device_id},
                cause=e,
            )

    def save_mobile_inbox_submission(
        self,
        user_id: str,
        device_id: str,
        device_name: str,
        submission_id: str,
        payload: Dict[str, Any],
        created_at_iso: str,
    ) -> None:
        """Persist a mobile inbox payload and update device last_seen_at."""
        try:
            self._ensure_user_exists(user_id)
            payload_json = json.dumps(payload or {})
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO mobile_inbox (
                        id, user_id, device_id, device_name, payload_json, status, created_at, processed_at
                    ) VALUES (?, ?, ?, ?, ?, 'pending', ?, NULL)
                    """,
                    (
                        submission_id,
                        user_id,
                        device_id,
                        device_name,
                        payload_json,
                        created_at_iso,
                    ),
                )
                conn.execute(
                    "UPDATE mobile_devices SET last_seen_at = ? WHERE user_id = ? AND device_id = ?",
                    (created_at_iso, user_id, device_id),
                )
                conn.commit()
        except Exception as e:
            self.logger.exception(
                "Error saving mobile inbox submission %s for user %s",
                submission_id,
                user_id,
            )
            raise DatabaseError(
                message="Error saving mobile inbox submission",
                details={"user_id": user_id, "submission_id": submission_id},
                cause=e,
            )

    def load_next_pending_mobile_inbox(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Return the oldest pending inbox submission for a user, if any."""
        try:
            with self._get_connection() as conn:
                conn.execute("BEGIN")
                cur = conn.execute(
                    """
                    SELECT id, device_id, device_name, payload_json, created_at
                    FROM mobile_inbox
                    WHERE user_id = ? AND status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT 1
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
                conn.commit()
            if not row:
                return None
            payload = None
            try:
                payload = (
                    json.loads(row["payload_json"]) if row["payload_json"] else None
                )
            except Exception:  # noqa: broad-except
                payload = None
            return {
                "id": row["id"],
                "device_id": row["device_id"],
                "device_name": row["device_name"],
                "payload": payload,
                "created_at": row["created_at"],
            }
        except Exception as e:
            self.logger.exception(
                "Error loading pending mobile inbox for user %s", user_id
            )
            raise DatabaseError(
                message="Error loading mobile inbox",
                details={"user_id": user_id},
                cause=e,
            )

    def get_pending_mobile_inbox_payload(
        self, user_id: str, submission_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch payload_json for a pending submission; returns decoded JSON or None."""
        try:
            with self._get_connection() as conn:
                conn.execute("BEGIN")
                cur = conn.execute(
                    "SELECT payload_json FROM mobile_inbox WHERE id = ? AND user_id = ? AND status = 'pending'",
                    (submission_id, user_id),
                )
                row = cur.fetchone()
                conn.commit()
            if not row:
                return None
            raw = row["payload_json"] if "payload_json" in row.keys() else row[0]
            if not raw:
                return {}
            try:
                payload = json.loads(raw)
            except Exception:
                payload = {}
            return payload if isinstance(payload, dict) else {}
        except Exception as e:
            self.logger.exception(
                "Error loading mobile inbox payload for user %s submission %s",
                user_id,
                submission_id,
            )
            raise DatabaseError(
                message="Error loading mobile inbox payload",
                details={"user_id": user_id, "submission_id": submission_id},
                cause=e,
            )

    def mark_mobile_inbox_approved(
        self,
        user_id: str,
        submission_id: str,
        result: Dict[str, Any],
        processed_at_iso: str,
    ) -> bool:
        """Mark a submission as approved and store result_json."""
        try:
            result_json = json.dumps(result or {})
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                cur = conn.execute(
                    """
                    UPDATE mobile_inbox
                    SET status = 'approved', processed_at = ?, result_json = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (processed_at_iso, result_json, submission_id, user_id),
                )
                conn.commit()
            return cur.rowcount > 0
        except Exception as e:
            self.logger.exception(
                "Error marking mobile inbox %s approved for user %s",
                submission_id,
                user_id,
            )
            raise DatabaseError(
                message="Error marking mobile inbox approved",
                details={"user_id": user_id, "submission_id": submission_id},
                cause=e,
            )

    def mark_mobile_inbox_rejected(
        self, user_id: str, submission_id: str, processed_at_iso: str
    ) -> bool:
        """Mark a pending submission as rejected."""
        try:
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                cur = conn.execute(
                    """
                    UPDATE mobile_inbox
                    SET status = 'rejected', processed_at = ?
                    WHERE id = ? AND user_id = ? AND status = 'pending'
                    """,
                    (processed_at_iso, submission_id, user_id),
                )
                conn.commit()
            return cur.rowcount > 0
        except Exception as e:
            self.logger.exception(
                "Error rejecting mobile inbox %s for user %s", submission_id, user_id
            )
            raise DatabaseError(
                message="Error rejecting mobile inbox",
                details={"user_id": user_id, "submission_id": submission_id},
                cause=e,
            )

    def get_mobile_inbox_status(
        self, user_id: str, submission_id: str
    ) -> Optional[Dict[str, Any]]:
        """Return status, processed_at and decoded result for a submission, or None."""
        try:
            with self._get_connection() as conn:
                conn.execute("BEGIN")
                cur = conn.execute(
                    """
                    SELECT status, processed_at, result_json
                    FROM mobile_inbox
                    WHERE id = ? AND user_id = ?
                    """,
                    (submission_id, user_id),
                )
                row = cur.fetchone()
                conn.commit()
            if not row:
                return None
            result = None
            raw = row["result_json"] if "result_json" in row.keys() else row[2]
            if raw:
                try:
                    result = json.loads(raw)
                except Exception:
                    result = None
            return {
                "status": row["status"],
                "processed_at": row["processed_at"],
                "result": result,
            }
        except Exception as e:
            self.logger.exception(
                "Error loading mobile inbox status for user %s submission %s",
                user_id,
                submission_id,
            )
            raise DatabaseError(
                message="Error loading mobile inbox status",
                details={"user_id": user_id, "submission_id": submission_id},
                cause=e,
            )

    def save_mobile_sync_request(
        self, user_id: str, request_id: str, expires_at_iso: str
    ) -> None:
        """Save a mobile sync request with TTL (5 minutes)"""
        try:
            self._ensure_user_exists(user_id)
            requested_at = datetime.now().isoformat()
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO mobile_sync_requests (
                        id, user_id, requested_at, expires_at, consumed_at
                    ) VALUES (?, ?, ?, ?, NULL)
                    """,
                    (request_id, user_id, requested_at, expires_at_iso),
                )
                conn.commit()
        except Exception as e:  # noqa: broad-except
            self.logger.exception(
                "Error saving mobile sync request for user %s", user_id
            )
            raise DatabaseError(
                message="Error saving mobile sync request",
                details={"user_id": user_id},
                cause=e,
            )

    def get_and_consume_mobile_sync_request(self, user_id: str) -> bool:
        """Atomically check and consume a mobile sync request. Returns True if request existed."""
        try:
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")

                # Check if request exists and not yet consumed
                cur = conn.execute(
                    """
                    SELECT id FROM mobile_sync_requests
                    WHERE user_id = ? AND consumed_at IS NULL AND expires_at > ?
                    LIMIT 1
                    """,
                    (user_id, datetime.now().isoformat()),
                )
                row = cur.fetchone()

                if not row:
                    conn.commit()
                    return False

                # Mark as consumed
                request_id = row["id"]
                conn.execute(
                    """
                    UPDATE mobile_sync_requests
                    SET consumed_at = ?
                    WHERE id = ?
                    """,
                    (datetime.now().isoformat(), request_id),
                )
                conn.commit()
                return True
        except Exception as e:
            self.logger.exception(
                "Error consuming mobile sync request for user %s", user_id
            )
            raise DatabaseError(
                message="Error consuming mobile sync request",
                details={"user_id": user_id},
                cause=e,
            )

    def cleanup_expired_sync_requests(self) -> int:
        """Delete expired sync requests. Returns count deleted."""
        try:
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                cur = conn.execute(
                    """
                    DELETE FROM mobile_sync_requests
                    WHERE expires_at < ?
                    """,
                    (datetime.now().isoformat(),),
                )
                count = cur.rowcount
                conn.commit()
                if count > 0:
                    self.logger.info(f"Cleaned up {count} expired sync requests")
                return count
        except Exception as e:
            self.logger.exception("Error cleaning up expired sync requests")
            raise DatabaseError(message="Error cleaning up sync requests", cause=e)

    def cleanup_stale_submissions(self, hours_old: int = 24) -> int:
        """Auto-reject submissions older than specified hours. Returns count rejected."""
        try:
            cutoff = (datetime.now() - timedelta(hours=hours_old)).isoformat()
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                cur = conn.execute(
                    """
                    UPDATE mobile_inbox
                    SET status = 'expired', processed_at = ?
                    WHERE status = 'pending' AND created_at < ?
                    """,
                    (datetime.now().isoformat(), cutoff),
                )
                count = cur.rowcount
                conn.commit()
                if count > 0:
                    self.logger.info(f"Auto-rejected {count} stale submissions")
                return count
        except Exception as e:
            self.logger.exception("Error cleaning up stale submissions")
            raise DatabaseError(message="Error cleaning up submissions", cause=e)

    def _migration_027_add_missing_indexes(self, conn) -> List[Dict[str, Any]]:
        """Migration 027: Add missing indexes for common queries"""
        migrations_applied = []
        try:
            # Add indexes for frequently queried columns
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_user_struck_forever ON tasks (user_id, struck_forever)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_user_struck_today ON tasks (user_id, struck_today)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_user_scheduled_date ON tasks (user_id, scheduled_date)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_tasks_user_project ON tasks (user_id, project)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_notes_user_created ON notes (user_id, created_at)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_notes_user_folder ON notes (user_id, folder_id)"
            )

            migrations_applied.append(
                {
                    "version": 27,
                    "description": "Added missing indexes for common queries (struck_forever, struck_today, scheduled_date, project, notes)",
                    "sql": "CREATE INDEX ...",
                }
            )

            self.logger.info("Migration 027 completed: Added 6 missing indexes")
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 027 failed: {e}")
            raise

    def _migration_028_task_nesting_parent_id(self, conn) -> List[Dict[str, Any]]:
        """Migration 028: Add parent_id column to tasks table for nesting/subtasks support."""
        migrations_applied: List[Dict[str, Any]] = []
        try:
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]

            if "parent_id" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN parent_id TEXT")
                self.logger.info("Added parent_id column to tasks table")

                # Create index for parent_id lookups
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_tasks_parent_id ON tasks (parent_id)"
                )
                self.logger.info("Created index on parent_id")

            migrations_applied.append(
                {
                    "version": 28,
                    "description": "Added parent_id column to tasks table for nesting support",
                    "sql": "ALTER TABLE tasks ADD COLUMN parent_id TEXT",
                }
            )
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 028 failed: {e}")
            raise

    def _migration_029_notes_nesting_parent_id(self, conn) -> List[Dict[str, Any]]:
        """Migration 029: Add parent_id column to notes table for nesting/hierarchy support."""
        migrations_applied: List[Dict[str, Any]] = []
        try:
            cursor = conn.execute("PRAGMA table_info(notes)")
            columns = [row[1] for row in cursor.fetchall()]

            if "parent_id" not in columns:
                conn.execute("ALTER TABLE notes ADD COLUMN parent_id TEXT")
                self.logger.info("Added parent_id column to notes table")

                # Create index for parent_id lookups
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_notes_parent_id ON notes (parent_id)"
                )
                self.logger.info("Created index on notes parent_id")

            migrations_applied.append(
                {
                    "version": 29,
                    "description": "Added parent_id column to notes table for nesting support",
                    "sql": "ALTER TABLE notes ADD COLUMN parent_id TEXT",
                }
            )
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 029 failed: {e}")
            raise

    def _migration_030_archived_tasks_table(self, conn) -> List[Dict[str, Any]]:
        """Migration 030: Create archived_tasks table for task archival system.

        This table mirrors the tasks table schema but is used for storing completed/archived tasks.
        Includes an archived_at timestamp and indexes for efficient queries.
        """
        migrations_applied: List[Dict[str, Any]] = []
        try:
            # Check if archived_tasks table already exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='archived_tasks'"
            )
            if not cursor.fetchone():
                # Create archived_tasks table with identical schema to tasks plus archived_at
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS archived_tasks (
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
                        refreshed_at TIMESTAMP,
                        recurrence_type TEXT,
                        recurrence_param TEXT,
                        snoozed_until TIMESTAMP,
                        subtasks TEXT,
                        parent_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                    )
                """)
                self.logger.info("Created archived_tasks table")

                # Create indexes for efficient queries
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_archived_tasks_user_id ON archived_tasks (user_id)"
                )
                self.logger.info("Created index on archived_tasks user_id")

                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_archived_tasks_archived_at ON archived_tasks (archived_at)"
                )
                self.logger.info("Created index on archived_tasks archived_at")

                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_archived_tasks_user_archived ON archived_tasks (user_id, archived_at DESC)"
                )
                self.logger.info(
                    "Created composite index on archived_tasks (user_id, archived_at)"
                )

            migrations_applied.append(
                {
                    "version": 30,
                    "description": "Created archived_tasks table for task archival system",
                    "sql": "CREATE TABLE archived_tasks (...)",
                }
            )
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 030 failed: {e}")
            raise

    # User Management Methods
    def create_user(
        self, user_id: str, username: str = None, password_hash: str = None
    ) -> bool:
        """Create a new user"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO users (id, username, password_hash, is_active)
                        VALUES (?, ?, ?, ?)
                    """,
                        (user_id, username or f"user_{user_id[:8]}", password_hash, 1),
                    )

                    # Create default settings
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
                self.logger.error(f"Error creating user {user_id}: {e}")
                return False

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user information by ID"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    cursor = conn.execute(
                        """
                        SELECT * FROM users WHERE id = ?
                    """,
                        (user_id,),
                    )

                    row = cursor.fetchone()
                    if row:
                        return {
                            "id": row["id"],
                            "username": row["username"],
                            "is_active": bool(row["is_active"]),
                            "created_at": row["created_at"],
                            "updated_at": row["updated_at"],
                        }
                    return None

            except Exception as e:
                self.logger.error(f"Error getting user {user_id}: {e}")
                return None

    def delete_user(self, user_id: str) -> bool:
        """Delete a user and all their data"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    # Delete user (cascades to tasks, settings, sessions)
                    cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
                    conn.commit()

                    if cursor.rowcount > 0:
                        self.logger.info(f"Deleted user: {user_id}")
                        return True
                    else:
                        self.logger.error(f"User {user_id} not found")
                        return False

            except Exception as e:
                self.logger.error(f"Error deleting user {user_id}: {e}")
                return False

    # Database maintenance methods
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    stats = {}

                    # Count users
                    cursor = conn.execute("SELECT COUNT(*) as count FROM users")
                    stats["users"] = cursor.fetchone()["count"]

                    # Count tasks
                    cursor = conn.execute("SELECT COUNT(*) as count FROM tasks")
                    stats["tasks"] = cursor.fetchone()["count"]

                    # Count sessions
                    cursor = conn.execute("SELECT COUNT(*) as count FROM sessions")
                    stats["sessions"] = cursor.fetchone()["count"]

                    # Database file size
                    if os.path.exists(self.db_path):
                        stats["db_size_mb"] = round(
                            os.path.getsize(self.db_path) / (1024 * 1024), 2
                        )

                    return stats

            except Exception as e:
                self.logger.exception("Error getting database stats")
                raise DatabaseError(
                    message="Error getting database stats",
                    details={"db_path": self.db_path},
                    cause=e,
                )

    def vacuum_database(self) -> bool:
        """Optimize database by running VACUUM"""
        with self._lock:
            try:
                with self._get_connection() as conn:
                    conn.execute("VACUUM")
                    conn.commit()
                    self.logger.info("Database vacuum completed")
                    return True

            except Exception as e:
                self.logger.exception("Error vacuuming database")
                raise DatabaseError(
                    message="Error vacuuming database",
                    details={"db_path": self.db_path},
                    cause=e,
                )

    def load_planner_v2_schedule(self, user_id: str) -> Dict[str, Any]:
        """Load scheduled tasks for Daily Planner v2"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT scheduled_tasks FROM planner_v2_schedule
                    WHERE user_id = ?
                """,
                    (user_id,),
                )

                result = cursor.fetchone()
                if result and result[0]:
                    return json.loads(result[0])
                else:
                    return {}

        except Exception as e:
            self.logger.exception(
                "Error loading planner v2 schedule for user %s", user_id
            )
            raise DatabaseError(
                message="Error loading planner v2 schedule",
                details={"user_id": user_id},
                cause=e,
            )

    def save_planner_v2_schedule(
        self, user_id: str, scheduled_tasks: Dict[str, Any]
    ) -> bool:
        """Save scheduled tasks for Daily Planner v2"""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Check if record exists
                cursor.execute(
                    """
                    SELECT id FROM planner_v2_schedule WHERE user_id = ?
                """,
                    (user_id,),
                )

                existing_record = cursor.fetchone()

                if existing_record:
                    # Update existing record
                    cursor.execute(
                        """
                        UPDATE planner_v2_schedule
                        SET scheduled_tasks = ?, updated_at = ?
                        WHERE user_id = ?
                    """,
                        (
                            json.dumps(scheduled_tasks),
                            datetime.now().isoformat(),
                            user_id,
                        ),
                    )
                else:
                    # Insert new record
                    cursor.execute(
                        """
                        INSERT INTO planner_v2_schedule (user_id, scheduled_tasks, created_at, updated_at)
                        VALUES (?, ?, ?, ?)
                    """,
                        (
                            user_id,
                            json.dumps(scheduled_tasks),
                            datetime.now().isoformat(),
                            datetime.now().isoformat(),
                        ),
                    )

                conn.commit()
                self.logger.info(
                    f"Successfully saved planner v2 schedule for user {user_id}"
                )
                return True

        except Exception as e:
            self.logger.exception(
                "Error saving planner v2 schedule for user %s", user_id
            )
            raise DatabaseError(
                message="Error saving planner v2 schedule",
                details={"user_id": user_id},
                cause=e,
            )

    def save_planner_history_snapshot(
        self, user_id: str, day: str, tasks: List[Dict[str, Any]]
    ) -> bool:
        try:
            self._ensure_user_exists(user_id)
            captured_at = datetime.now().isoformat()

            def to_int(value):
                try:
                    return int(value) if value is not None else None
                except Exception:  # noqa: broad-except - Data layer defensive exception handling
                    return None

            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")

                conn.execute(
                    "DELETE FROM planner_task_history WHERE user_id = ? AND day = ?",
                    (user_id, day),
                )

                for t in tasks or []:
                    task_id = t.get("id")
                    if not task_id:
                        continue

                    scheduled_hour = to_int(t.get("scheduled_hour"))
                    scheduled_minute = to_int(t.get("scheduled_minute"))
                    scheduled_duration = to_int(t.get("scheduled_duration"))

                    daily_strikes = t.get("daily_strikes") or {}
                    strikes_for_day = 0
                    try:
                        strikes_for_day = int(daily_strikes.get(day, 0) or 0)
                    except Exception:  # noqa: broad-except - Data layer defensive exception handling
                        strikes_for_day = 0

                    completed = bool(t.get("completed", False))
                    strike_mode = "none"
                    if completed:
                        strike_mode = "forever"
                    elif strikes_for_day > 0:
                        strike_mode = "today"

                    conn.execute(
                        """
                        INSERT INTO planner_task_history (
                            user_id, day, task_id, title,
                            scheduled_hour, scheduled_minute, scheduled_duration,
                            strike_mode, strikes_for_day, completed, strike_report,
                            captured_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            user_id,
                            day,
                            task_id,
                            t.get("title", ""),
                            scheduled_hour,
                            scheduled_minute,
                            scheduled_duration,
                            strike_mode,
                            strikes_for_day,
                            1 if completed else 0,
                            t.get("strike_report"),
                            captured_at,
                        ),
                    )

                conn.execute(
                    """
                    DELETE FROM planner_task_history
                    WHERE user_id = ?
                      AND day NOT IN (
                        SELECT day FROM planner_task_history
                        WHERE user_id = ?
                        GROUP BY day
                        ORDER BY day DESC
                        LIMIT 7
                      )
                    """,
                    (user_id, user_id),
                )

                conn.commit()
                return True
        except Exception as e:
            self.logger.exception("Error saving planner history snapshot")
            raise DatabaseError(
                message="Error saving planner history snapshot",
                details={"user_id": user_id, "day": day},
                cause=e,
            )

    def load_planner_history_days(self, user_id: str, limit: int = 7) -> List[str]:
        try:
            self._ensure_user_exists(user_id)
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT day
                    FROM planner_task_history
                    WHERE user_id = ?
                    GROUP BY day
                    ORDER BY day DESC
                    LIMIT ?
                    """,
                    (user_id, int(limit)),
                )
                return [row["day"] for row in cursor.fetchall() if row and row["day"]]
        except Exception as e:
            self.logger.exception("Error loading planner history days")
            raise DatabaseError(
                message="Error loading planner history days",
                details={"user_id": user_id, "limit": limit},
                cause=e,
            )

    def load_planner_history_for_day(
        self, user_id: str, day: str
    ) -> List[Dict[str, Any]]:
        try:
            self._ensure_user_exists(user_id)
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT task_id, title, scheduled_hour, scheduled_minute, scheduled_duration,
                           strike_mode, strikes_for_day, completed, strike_report, captured_at
                    FROM planner_task_history
                    WHERE user_id = ? AND day = ?
                    ORDER BY scheduled_hour ASC, scheduled_minute ASC, title ASC
                    """,
                    (user_id, day),
                )
                rows = cursor.fetchall()
                items = []
                for row in rows:
                    items.append(
                        {
                            "task_id": row["task_id"],
                            "title": row["title"] or "",
                            "scheduled_hour": row["scheduled_hour"],
                            "scheduled_minute": row["scheduled_minute"],
                            "scheduled_duration": row["scheduled_duration"],
                            "strike_mode": row["strike_mode"] or "none",
                            "strikes_for_day": row["strikes_for_day"]
                            if row["strikes_for_day"] is not None
                            else 0,
                            "completed": bool(row["completed"]),
                            "strike_report": row["strike_report"],
                            "captured_at": row["captured_at"],
                            "day": day,
                        }
                    )
                return items
        except Exception as e:
            self.logger.exception("Error loading planner history for day %s", day)
            raise DatabaseError(
                message="Error loading planner history for day",
                details={"user_id": user_id, "day": day},
                cause=e,
            )

    def add_strike_today_report_event(
        self, user_id: str, task_id: str, day: str, strike_number: int, report: str
    ) -> bool:
        try:
            self._ensure_user_exists(user_id)
            if not task_id:
                return False
            created_at = datetime.now().isoformat()
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                conn.execute(
                    """
                    INSERT INTO strike_today_report_history (user_id, task_id, day, strike_number, report, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        task_id,
                        day,
                        int(strike_number or 0),
                        report or "",
                        created_at,
                    ),
                )
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(
                f"Error adding strike report event for task {task_id}: {e}"
            )
            return False

    def load_strike_today_report_history(
        self, user_id: str, task_id: str, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        try:
            self._ensure_user_exists(user_id)
            if not task_id:
                return []
            limit = int(limit) if limit is not None else 100
            offset = int(offset) if offset is not None else 0
            if limit <= 0:
                limit = 100
            if limit > 500:
                limit = 500
            if offset < 0:
                offset = 0

            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT id, task_id, day, strike_number, report, created_at
                    FROM strike_today_report_history
                    WHERE user_id = ? AND task_id = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (user_id, task_id, limit, offset),
                )
                rows = cursor.fetchall()
                items = []
                for row in rows:
                    items.append(
                        {
                            "id": row["id"],
                            "task_id": row["task_id"],
                            "day": row["day"],
                            "strike_number": row["strike_number"],
                            "report": row["report"] or "",
                            "created_at": row["created_at"],
                        }
                    )
                return items
        except Exception as e:
            self.logger.exception(
                "Error loading strike report history for task %s", task_id
            )
            raise DatabaseError(
                message="Error loading strike report history",
                details={"user_id": user_id, "task_id": task_id},
                cause=e,
            )

    def add_strike_event(
        self, user_id: str, task_id: str, day: str, strike_type: str
    ) -> bool:
        try:
            self._ensure_user_exists(user_id)
            if not user_id or not task_id or not day:
                return False
            if strike_type not in ("today", "forever"):
                return False
            created_at = datetime.now().isoformat()
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                conn.execute(
                    """
                    INSERT INTO strike_events (user_id, task_id, day, strike_type, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (user_id, task_id, day, strike_type, created_at),
                )
                conn.commit()
                return True
        except Exception as e:
            self.logger.exception("Error adding strike event for task %s", task_id)
            raise DatabaseError(
                message="Error adding strike event",
                details={"user_id": user_id, "task_id": task_id},
                cause=e,
            )

    def add_settings_change_event(
        self,
        user_id: str,
        setting_key: str = "general",
        old_value: str = None,
        new_value: str = None,
    ) -> bool:
        """Record a settings change event for streak tracking."""
        try:
            self._ensure_user_exists(user_id)
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                day = datetime.now().strftime("%Y-%m-%d")
                created_at = datetime.now().isoformat()

                # Used by daily recap/analytics counters
                conn.execute(
                    """
                    INSERT INTO settings_change_events (user_id, day, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, day, created_at),
                )

                # Used by streak calculation when count_settings=True
                conn.execute(
                    """
                    INSERT INTO settings_events (user_id, setting_key, old_value, new_value, timestamp)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (user_id, setting_key, old_value, new_value),
                )
                conn.commit()
                return True
        except Exception as e:
            self.logger.exception(
                "Error adding settings change event for user %s", user_id
            )
            raise DatabaseError(
                message="Error adding settings change event",
                details={"user_id": user_id},
                cause=e,
            )

    def record_user_heartbeat(self, user_id: str) -> bool:
        """Record user activity heartbeat for active users tracking."""
        try:
            self._ensure_user_exists(user_id)
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                now = datetime.now().isoformat()

                # Insert or update the heartbeat timestamp
                conn.execute(
                    """
                    INSERT OR REPLACE INTO user_heartbeat (user_id, last_seen_at)
                    VALUES (?, ?)
                    """,
                    (user_id, now),
                )
                conn.commit()
                return True
        except Exception as e:
            self.logger.exception("Error recording heartbeat for user %s", user_id)
            raise DatabaseError(
                message="Error recording heartbeat",
                details={"user_id": user_id},
                cause=e,
            )

    def count_active_users(self, minutes: int = 2) -> int:
        """Count users active in the last N minutes."""
        try:
            with self._get_connection() as conn:
                # Calculate the timestamp for N minutes ago
                cutoff_time = (datetime.now() - timedelta(minutes=minutes)).isoformat()

                cursor = conn.execute(
                    """
                    SELECT COUNT(*) as active_count
                    FROM user_heartbeat
                    WHERE last_seen_at > ?
                    """,
                    (cutoff_time,),
                )
                result = cursor.fetchone()
                return result["active_count"] if result else 0
        except Exception as e:
            self.logger.exception("Error counting active users")
            raise DatabaseError(message="Error counting active users", cause=e)

    def count_installed_users(self) -> int:
        """Count total number of unique users who have installed/accessed the app."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT COUNT(DISTINCT user_id) as installed_count
                    FROM users
                    """
                )
                result = cursor.fetchone()
                return result["installed_count"] if result else 0
        except Exception as e:
            self.logger.exception("Error counting installed users")
            raise DatabaseError(message="Error counting installed users", cause=e)

    def get_strike_contributions_for_month(
        self, user_id: str, month: str
    ) -> Dict[str, Any]:
        try:
            self._ensure_user_exists(user_id)
            if not month or not isinstance(month, str) or len(month) != 7:
                raise ValidationError(message="Invalid month")

            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT day, COUNT(DISTINCT task_id) AS c
                    FROM strike_events
                    WHERE user_id = ? AND day LIKE ?
                    GROUP BY day
                    ORDER BY day ASC
                    """,
                    (user_id, f"{month}-%"),
                )
                rows = cursor.fetchall()
                days: Dict[str, int] = {}
                max_c = 0
                for r in rows:
                    d = r["day"]
                    c = int(r["c"] or 0)
                    days[d] = c
                    if c > max_c:
                        max_c = c

                cursor = conn.execute(
                    """
                    SELECT SUBSTR(created_at, 1, 10) AS day, COUNT(*) AS c
                    FROM tasks
                    WHERE user_id = ? AND SUBSTR(created_at, 1, 7) = ?
                    GROUP BY day
                    ORDER BY day ASC
                    """,
                    (user_id, month),
                )
                rows = cursor.fetchall()
                added: Dict[str, int] = {}
                for r in rows:
                    d = r["day"]
                    c = int(r["c"] or 0)
                    if d:
                        added[d] = c

                return {"month": month, "days": days, "added": added, "max": max_c}
        except Exception as e:
            self.logger.exception(
                "Error loading strike contributions for month %s", month
            )
            raise DatabaseError(
                message="Error loading strike contributions",
                details={"user_id": user_id, "month": month},
                cause=e,
            )

    def list_strike_contribution_months(
        self, user_id: str, limit: int = 24
    ) -> List[str]:
        try:
            self._ensure_user_exists(user_id)
            limit = int(limit or 24)
            if limit <= 0:
                limit = 24
            if limit > 120:
                limit = 120
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT SUBSTR(day, 1, 7) AS m
                    FROM strike_events
                    WHERE user_id = ?
                    GROUP BY m
                    ORDER BY m DESC
                    LIMIT ?
                    """,
                    (user_id, limit),
                )
                rows = cursor.fetchall()
                return [r["m"] for r in rows if r["m"]]
        except Exception as e:
            self.logger.exception("Error listing strike contribution months")
            raise DatabaseError(
                message="Error listing strike contribution months",
                details={"user_id": user_id, "limit": limit},
                cause=e,
            )

    def save_daily_reset_log(
        self,
        user_id: str,
        reset_at_iso: str,
        tasks: List[Dict[str, Any]],
        reset_reason: str = "scheduled",
    ) -> bool:
        """Persist a compact summary of tasks affected by a daily reset."""
        try:
            self._ensure_user_exists(user_id)
            if not tasks:
                return False

            # Sanitize task summaries to avoid unbounded log growth.
            summaries: List[Dict[str, Any]] = []
            for t in tasks[:500]:
                if not isinstance(t, dict):
                    continue
                summaries.append(
                    {
                        "id": str(t.get("id") or "").strip(),
                        "title": (t.get("title") or "").strip(),
                        "project": (t.get("project") or "").strip(),
                        "due_date": t.get("due_date"),
                        "scheduled_date": t.get("scheduled_date"),
                        "strike_count": int(t.get("strike_count") or 0),
                        "completed": bool(t.get("completed", False)),
                        "struck_forever": bool(t.get("struck_forever", False)),
                    }
                )

            if not summaries:
                return False

            payload = json.dumps(summaries)
            created_at = datetime.now().isoformat()
            reset_at_value = reset_at_iso or created_at

            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                conn.execute(
                    """
                    INSERT INTO daily_reset_log (
                        user_id, reset_at, task_count, tasks_json, seen, reset_reason, created_at
                    ) VALUES (?, ?, ?, ?, 0, ?, ?)
                    """,
                    (
                        user_id,
                        reset_at_value,
                        len(summaries),
                        payload,
                        reset_reason or None,
                        created_at,
                    ),
                )
                # Keep only the most recent 30 reset logs per user.
                conn.execute(
                    """
                    DELETE FROM daily_reset_log
                    WHERE user_id = ?
                      AND id NOT IN (
                        SELECT id FROM daily_reset_log
                        WHERE user_id = ?
                        ORDER BY reset_at DESC, id DESC
                        LIMIT 30
                      )
                    """,
                    (user_id, user_id),
                )
                conn.commit()
            return True
        except Exception as e:
            self.logger.exception("Error saving daily reset log for user %s", user_id)
            raise DatabaseError(
                message="Error saving daily reset log",
                details={"user_id": user_id},
                cause=e,
            )

    def get_latest_daily_reset_log(
        self, user_id: str, include_seen: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Return the latest daily reset log for a user, optionally including seen entries."""
        try:
            self._ensure_user_exists(user_id)
            with self._get_connection() as conn:
                conn.execute("BEGIN")
                if include_seen:
                    cur = conn.execute(
                        """
                        SELECT id, reset_at, task_count, tasks_json, seen, reset_reason
                        FROM daily_reset_log
                        WHERE user_id = ?
                        ORDER BY reset_at DESC, id DESC
                        LIMIT 1
                        """,
                        (user_id,),
                    )
                else:
                    cur = conn.execute(
                        """
                        SELECT id, reset_at, task_count, tasks_json, seen, reset_reason
                        FROM daily_reset_log
                        WHERE user_id = ? AND seen = 0
                        ORDER BY reset_at DESC, id DESC
                        LIMIT 1
                        """,
                        (user_id,),
                    )
                row = cur.fetchone()
                conn.commit()
            if not row:
                return None
            raw_json = row["tasks_json"] if "tasks_json" in row.keys() else row[3]
            try:
                tasks = json.loads(raw_json) if raw_json else []
            except Exception:
                tasks = []
            if not isinstance(tasks, list):
                tasks = []
            return {
                "id": row["id"],
                "reset_at": row["reset_at"],
                "task_count": row["task_count"],
                "tasks": tasks,
                "seen": bool(row["seen"]),
                "reset_reason": row["reset_reason"],
            }
        except Exception as e:
            self.logger.exception(
                "Error loading latest daily reset log for user %s", user_id
            )
            raise DatabaseError(
                message="Error loading daily reset log",
                details={"user_id": user_id, "include_seen": include_seen},
                cause=e,
            )

    def mark_daily_reset_log_seen(
        self, user_id: str, log_id: Optional[int] = None
    ) -> bool:
        """Mark a daily reset log (or all logs) as seen for a user."""
        try:
            self._ensure_user_exists(user_id)
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                if log_id is None:
                    cur = conn.execute(
                        """
                        UPDATE daily_reset_log
                        SET seen = 1
                        WHERE user_id = ? AND seen = 0
                        """,
                        (user_id,),
                    )
                else:
                    cur = conn.execute(
                        """
                        UPDATE daily_reset_log
                        SET seen = 1
                        WHERE user_id = ? AND id = ?
                        """,
                        (user_id, int(log_id)),
                    )
                conn.commit()
            return cur.rowcount > 0
        except Exception as e:
            self.logger.exception(
                "Error marking daily reset log seen for user %s", user_id
            )
            raise DatabaseError(
                message="Error marking daily reset log seen",
                details={"user_id": user_id, "log_id": log_id},
                cause=e,
            )

    def get_latest_notes_cleaner_status(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Return a compact status object for the most recent notes-cleaner run.

        This is persisted in the daily_reset_log table using a synthetic
        reset_reason of 'notes_cleaner' and a small payload summarizing the run
        in tasks_json.
        """
        try:
            self._ensure_user_exists(user_id)
            with self._get_connection() as conn:
                conn.execute("BEGIN")
                cur = conn.execute(
                    """
                    SELECT reset_at, task_count, tasks_json
                    FROM daily_reset_log
                    WHERE user_id = ? AND reset_reason = 'notes_cleaner'
                    ORDER BY reset_at DESC, id DESC
                    LIMIT 1
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
                conn.commit()
            if not row:
                return None

            raw_json = row["tasks_json"] if "tasks_json" in row.keys() else row[2]
            cleaned_count = 0
            try:
                payload = json.loads(raw_json) if raw_json else {}
                if isinstance(payload, dict) and "cleaned_count" in payload:
                    cleaned_count = int(payload.get("cleaned_count") or 0)
            except Exception:
                cleaned_count = 0

            return {
                "ran_at": row["reset_at"],
                "cleaned_count": cleaned_count,
            }
        except Exception as e:
            self.logger.exception(
                "Error loading latest notes cleaner status for user %s", user_id
            )
            raise DatabaseError(
                message="Error loading notes cleaner status",
                details={"user_id": user_id},
                cause=e,
            )

    def was_recap_seen(self, user_id: str, recap_day: str) -> bool:
        try:
            self._ensure_user_exists(user_id)
            if not recap_day:
                return False
            with self._get_connection() as conn:
                cur = conn.execute(
                    "SELECT 1 FROM recap_seen WHERE user_id = ? AND recap_day = ? LIMIT 1",
                    (user_id, recap_day),
                )
                return cur.fetchone() is not None
        except Exception as e:
            self.logger.exception("Error checking recap seen")
            raise DatabaseError(
                message="Error checking recap seen",
                details={"user_id": user_id, "recap_day": recap_day},
                cause=e,
            )

    def mark_recap_seen(self, user_id: str, recap_day: str) -> bool:
        try:
            self._ensure_user_exists(user_id)
            if not recap_day:
                return False
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                conn.execute(
                    """
                    INSERT OR REPLACE INTO recap_seen (user_id, recap_day, seen_at)
                    VALUES (?, ?, ?)
                    """,
                    (user_id, recap_day, datetime.now().isoformat()),
                )
                conn.commit()
                return True
        except Exception as e:
            self.logger.exception("Error marking recap seen for %s", recap_day)
            raise DatabaseError(
                message="Error marking recap seen",
                details={"user_id": user_id, "recap_day": recap_day},
                cause=e,
            )

    def get_daily_recap(self, user_id: str, day: str) -> Dict[str, Any]:
        try:
            self._ensure_user_exists(user_id)
            if not day:
                raise ValidationError(message="Invalid day")

            with self._get_connection() as conn:
                # Optimized: Single query with subqueries instead of N+1 pattern
                cur = conn.execute(
                    """
                    SELECT
                        (SELECT COUNT(DISTINCT task_id)
                         FROM strike_events
                         WHERE user_id = ? AND day = ?) AS struck,
                        (SELECT COUNT(DISTINCT task_id)
                         FROM strike_events
                         WHERE user_id = ? AND day = ? AND strike_type = 'forever') AS completed_forever,
                        (SELECT COUNT(*)
                         FROM tasks
                         WHERE user_id = ? AND SUBSTR(created_at, 1, 10) = ?) AS tasks_added,
                        (SELECT COUNT(*)
                         FROM settings_change_events
                         WHERE user_id = ? AND day = ?) AS settings_changed,
                        (SELECT COUNT(*)
                         FROM notes
                         WHERE user_id = ? AND SUBSTR(created_at, 1, 10) = ?) AS notes_added,
                        (SELECT COUNT(DISTINCT task_id)
                         FROM planner_task_history
                         WHERE user_id = ? AND day = ?) AS planned_tasks
                    """,
                    (
                        user_id,
                        day,
                        user_id,
                        day,
                        user_id,
                        day,
                        user_id,
                        day,
                        user_id,
                        day,
                        user_id,
                        day,
                    ),
                )
                row = cur.fetchone()

                struck = int(row["struck"] or 0)
                completed_forever = int(row["completed_forever"] or 0)
                tasks_added = int(row["tasks_added"] or 0)
                settings_changed = int(row["settings_changed"] or 0)
                notes_added = int(row["notes_added"] or 0)
                planned_tasks = int(row["planned_tasks"] or 0)

                streak_days = self._calculate_streak_days_from_tasks(conn, user_id, day)

                return {
                    "day": day,
                    "tasks_striked": struck,
                    "tasks_completed_forever": completed_forever,
                    "new_tasks_added": tasks_added,
                    "settings_changed": settings_changed,
                    "tasks_planned": planned_tasks,
                    "notes_added": notes_added,
                    "streak_days": streak_days,
                    "tasks_retried": 0,  # Will be populated when retry tracking is implemented
                }
        except Exception as e:
            self.logger.exception("Error building daily recap for %s", day)
            raise DatabaseError(
                message="Error building daily recap",
                details={"user_id": user_id, "day": day},
                cause=e,
            )

    def save_recap_feedback(
        self, user_id: str, recap_day: str, answers: Dict[str, Any]
    ) -> bool:
        """Persist feedback answers for a given recap day.

        ``answers`` is a dict of {question_key: answer_string} e.g.:
            {'went_well': '...', 'improve_tomorrow': '...', 'mood_rating': '4'}

        Each key/value pair is upserted individually so partial saves are safe.
        Silently ignores empty-string keys or non-string values.
        """
        try:
            self._ensure_user_exists(user_id)
            if not recap_day or not isinstance(answers, dict) or not answers:
                return False
            now = datetime.now().isoformat()
            with self._get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                for key, value in answers.items():
                    key = str(key or "").strip()
                    if not key:
                        continue
                    answer_str = str(value) if value is not None else ""
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO daily_recap_feedback
                            (user_id, recap_day, question_key, answer, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (user_id, recap_day, key, answer_str, now),
                    )
                conn.commit()
            return True
        except Exception as e:
            self.logger.exception(
                "Error saving recap feedback for user %s day %s", user_id, recap_day
            )
            raise DatabaseError(
                message="Error saving recap feedback",
                details={"user_id": user_id, "recap_day": recap_day},
                cause=e,
            )

    def load_recap_feedback(self, user_id: str, recap_day: str) -> Dict[str, str]:
        """Return previously saved feedback answers for a given recap day.

        Returns a dict ``{question_key: answer}``; empty dict if nothing saved.
        """
        try:
            self._ensure_user_exists(user_id)
            if not recap_day:
                return {}
            with self._get_connection() as conn:
                cur = conn.execute(
                    """
                    SELECT question_key, answer
                    FROM daily_recap_feedback
                    WHERE user_id = ? AND recap_day = ?
                    """,
                    (user_id, recap_day),
                )
                rows = cur.fetchall()
            return {row["question_key"]: (row["answer"] or "") for row in rows}
        except Exception as e:
            self.logger.exception(
                "Error loading recap feedback for user %s day %s", user_id, recap_day
            )
            raise DatabaseError(
                message="Error loading recap feedback",
                details={"user_id": user_id, "recap_day": recap_day},
                cause=e,
            )

    def _calculate_streak_days_from_tasks(
        self, conn, user_id: str, up_to_day: str
    ) -> int:
        cur = conn.execute(
            """
            SELECT DISTINCT SUBSTR(completed_at, 1, 10) AS d
            FROM tasks
            WHERE user_id = ? AND completed = 1 AND completed_at IS NOT NULL
            ORDER BY d DESC
            """,
            (user_id,),
        )
        rows = cur.fetchall() or []
        completion_days = [r["d"] for r in rows if r["d"]]
        if not completion_days:
            return 0

        try:
            anchor = datetime.strptime(up_to_day, "%Y-%m-%d").date()
        except Exception:  # noqa: broad-except - Data layer defensive exception handling
            anchor = datetime.now().date()

        days_set = set(completion_days)
        streak = 0
        while True:
            d = anchor - timedelta(days=streak)
            if d.isoformat() in days_set:
                streak += 1
                continue
            break
        return streak
