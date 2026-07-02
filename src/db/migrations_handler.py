"""Database migration handler for Shakshuka task management application.

Manages database schema evolution and version tracking. Handles migration
execution, backup/restore, and backward compatibility.
"""

import os
import shutil
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from src.constants import (
    BACKUP_RETENTION_DAYS,
    DB_CONNECTION_TIMEOUT,
    MAX_BACKUP_SIZE_BYTES,
)
from src.exceptions import DatabaseError, ValidationError

# Configure logging
import logging

logger = logging.getLogger(__name__)


class MigrationsHandler:
    """Handles database migrations, version management, and backups."""

    def __init__(self, db_path: str):
        """Initialize migrations handler.

        Args:
            db_path: Path to the SQLite database file
        """
        if not db_path or not isinstance(db_path, str):
            raise ValidationError(message="Invalid db_path")
        self.db_path = db_path
        self.logger = logger

    def run_migrations(self, get_connection: Callable) -> None:
        """Run database migrations with comprehensive error handling and rollback.

        Args:
            get_connection: Callable that returns a database connection
        """
        migration_version = None
        backup_created = False

        try:
            with get_connection() as conn:
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
                        migrations_applied.extend(self._migration_001_analytics_columns(conn))

                    # Migration 2: Add indexes and constraints
                    if migration_version < 2:
                        migrations_applied.extend(self._migration_002_indexes_constraints(conn))

                    # Migration 3: Add user preferences
                    if migration_version < 3:
                        migrations_applied.extend(self._migration_003_user_preferences(conn))

                    # Migration 4: Add audit trail
                    if migration_version < 4:
                        migrations_applied.extend(self._migration_004_audit_trail(conn))

                    # Migration 5: Add planner v2 tables
                    if migration_version < 5:
                        migrations_applied.extend(self._migration_005_planner_v2(conn))

                    # Migration 6: Add scheduled_date and scheduled_minute fields
                    if migration_version < 6:
                        migrations_applied.extend(self._migration_006_scheduled_fields(conn))

                    # Migration 7: Add daily_strikes column to persist per-day strike counts
                    if migration_version < 7:
                        migrations_applied.extend(self._migration_007_daily_strikes(conn))

                    # Migration 8: Add planner daily history snapshots
                    if migration_version < 8:
                        migrations_applied.extend(self._migration_008_planner_history(conn))

                    # Migration 9: Add strike-today report history events
                    if migration_version < 9:
                        migrations_applied.extend(self._migration_009_strike_report_history(conn))

                    # Migration 10: Add struck_forever column to tasks table
                    if migration_version < 10:
                        migrations_applied.extend(self._migration_010_struck_forever(conn))

                    # Migration 11: Add analytics history tables for strike calendar and daily recap
                    if migration_version < 11:
                        migrations_applied.extend(self._migration_011_analytics_history(conn))

                    # Migration 12: Add refreshed_at column for daily reset badge
                    if migration_version < 12:
                        migrations_applied.extend(self._migration_012_refreshed_at(conn))

                    # Migration 13: Add last_daily_reset_at to user_preferences/settings
                    if migration_version < 13:
                        migrations_applied.extend(self._migration_013_last_daily_reset_at(conn))

                    # Migration 14: Add mobile inbox tables
                    if migration_version < 14:
                        migrations_applied.extend(self._migration_014_mobile_inbox(conn))

                    # Migration 15: Add settings_events table for streak tracking
                    if migration_version < 15:
                        migrations_applied.extend(self._migration_015_settings_events(conn))

                    # Migration 16: Add deleted_tasks table
                    if migration_version < 16:
                        migrations_applied.extend(self._migration_016_deleted_tasks(conn))

                    # Migration 17: Add daily_reset_count column
                    if migration_version < 17:
                        migrations_applied.extend(self._migration_017_daily_reset_count(conn))

                    # Migration 18: Add folder support for notes (explorer-style dashboard)
                    if migration_version < 18:
                        migrations_applied.extend(self._migration_018_notes_folders(conn))

                    # Migration 19: Create daily_reset_log table for daily reset summaries
                    if migration_version < 19:
                        migrations_applied.extend(self._migration_019_daily_reset_log(conn))

                    # Migration 20: Add recurrence/snooze fields to tasks
                    if migration_version < 20:
                        migrations_applied.extend(self._migration_020_tasks_recurrence_snooze(conn))

                    # Migration 21: Add pinned/archived flags to notes
                    if migration_version < 21:
                        migrations_applied.extend(self._migration_021_notes_pin_archive(conn))

                    # Migration 22: Add daily_recap_feedback table
                    if migration_version < 22:
                        migrations_applied.extend(self._migration_022_daily_recap_feedback(conn))

                    # Migration 23: Add compact_mode setting
                    if migration_version < 23:
                        migrations_applied.extend(self._migration_023_compact_mode_setting(conn))

                    # Migration 24: Notes trash, version history, task subtasks
                    if migration_version < 24:
                        migrations_applied.extend(self._migration_024_notes_trash_versions_subtasks(conn))

                    # Migration 25: Add owner column to tasks
                    if migration_version < 25:
                        migrations_applied.extend(self._migration_025_owner_column(conn))

                    # Migration 26: Add mobile_sync_requests table and sequence_num to mobile_inbox
                    if migration_version < 26:
                        migrations_applied.extend(self._migration_026_mobile_sync_requests(conn))

                    # Migration 27: Add missing indexes for common queries
                    if migration_version < 27:
                        migrations_applied.extend(self._migration_027_add_missing_indexes(conn))

                    # Migration 28: Add parent_id for task nesting
                    if migration_version < 28:
                        migrations_applied.extend(self._migration_028_task_nesting_parent_id(conn))

                    # Migration 29: Add parent_id for notes nesting
                    if migration_version < 29:
                        migrations_applied.extend(self._migration_029_notes_nesting_parent_id(conn))

                    # Migration 30: Create archived_tasks table for task archival system
                    if migration_version < 30:
                        migrations_applied.extend(self._migration_030_archived_tasks_table(conn))

                    # Migration 31: Add split content status tracking to tasks and notes
                    if migration_version < 31:
                        migrations_applied.extend(self._migration_031_split_content_tracking(conn))

                    # Migration 32: Decode existing split-encoded content in tasks and notes
                    if migration_version < 32:
                        migrations_applied.extend(self._migration_032_decode_split_content(conn))

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
                    except Exception:  # noqa: broad-except
                        self.logger.exception("Migration rollback failed")
                    self.logger.exception("Migration transaction failed")

                    # Restore backup if created
                    if backup_created:
                        try:
                            self._restore_migration_backup(get_connection)
                            self.logger.info("Migration backup restored successfully")
                        except Exception as restore_e:
                            self.logger.error(f"Failed to restore migration backup: {restore_e}")

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

    def _get_migration_version(self, conn) -> int:
        """Get current migration version from database."""
        try:
            cursor = conn.execute(
                "SELECT version FROM migration_version ORDER BY version DESC LIMIT 1"
            )
            result = cursor.fetchone()
            return result[0] if result else 0
        except sqlite3.OperationalError:
            # Migration version table doesn't exist, create it
            self.logger.info("migration_version table missing; creating")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS migration_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    description TEXT
                )
            """
            )
            conn.execute(
                'INSERT INTO migration_version (version, description) VALUES (0, "Initial version")'
            )
            return 0

    def _update_migration_version(self, conn, version: int):
        """Update migration version in database."""
        conn.execute(
            "INSERT OR REPLACE INTO migration_version (version, description) VALUES (?, ?)",
            (version, f"Migration {version} applied"),
        )

    def _create_migration_backup(self, conn) -> bool:
        """Create backup before major migrations."""
        try:
            backup_path = f"{self.db_path}.migration_backup_{int(time.time())}"

            # Create backup by copying database file
            shutil.copy2(self.db_path, backup_path)

            # Store backup path for potential restoration
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS migration_backups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    backup_path TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    migration_version INTEGER
                )
            """
            )

            current_version = self._get_migration_version(conn)
            conn.execute(
                "INSERT INTO migration_backups (backup_path, migration_version) VALUES (?, ?)",
                (backup_path, current_version),
            )

            # Clean up old backups
            self._cleanup_old_backups(conn)

            return True
        except Exception as e:
            self.logger.error("Failed to create migration backup: %s", e)
            return False

    def _cleanup_old_backups(self, conn):
        """Clean up old migration backups."""
        try:
            # Get all backups
            cursor = conn.execute(
                """
                SELECT id, backup_path, created_at
                FROM migration_backups
                ORDER BY created_at DESC
            """
            )
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

                    # Compare in local time
                    try:
                        if created_dt.tzinfo is not None:
                            created_dt_local = created_dt.astimezone().replace(
                                tzinfo=None
                            )
                        else:
                            created_dt_local = created_dt
                    except Exception:  # noqa: broad-except
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

    def _restore_migration_backup(self, get_connection: Callable):
        """Restore from migration backup."""
        try:
            with get_connection() as conn:
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
        """Verify database integrity."""
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

    # Migration methods (001-032)
    def _migration_001_analytics_columns(self, conn) -> List[Dict]:
        """Migration 1: Add analytics columns to tasks table."""
        migrations_applied = []
        try:
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]

            analytics_columns = [
                ("completed_at", "TIMESTAMP"),
                ("struck_today", "BOOLEAN DEFAULT 0"),
                ("struck_date", "TIMESTAMP"),
                ("strike_report", "TEXT"),
                ("strike_count", "INTEGER DEFAULT 0"),
            ]

            for column_name, column_def in analytics_columns:
                if column_name not in columns:
                    if column_name in [col[0] for col in analytics_columns]:
                        conn.execute(f"ALTER TABLE tasks ADD COLUMN {column_name} {column_def}")
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
        """Migration 2: Add indexes and constraints for performance."""
        migrations_applied = []
        try:
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
        """Migration 3: Add user preferences table."""
        migrations_applied = []
        try:
            conn.execute(
                """
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
            """
            )

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
        """Migration 4: Add audit trail table."""
        migrations_applied = []
        try:
            conn.execute(
                """
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
            """
            )

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
        """Migration 5: Add planner v2 tables."""
        migrations_applied = []
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS planner_v2_schedule (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    scheduled_tasks TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(user_id)
                )
            """
            )

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
        """Migration 6: Add scheduled_date and scheduled_minute fields to tasks table."""
        migrations_applied = []
        try:
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]

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
        """Migration 7: Add daily_strikes TEXT column to tasks for per-day strike tracking."""
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
        """Migration 8: Add planner daily history snapshots."""
        migrations_applied = []
        try:
            conn.execute(
                """
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
            """
            )
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
        """Migration 9: Add strike-today report history events."""
        migrations_applied = []
        try:
            conn.execute(
                """
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
            """
            )
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
        """Migration 10: Add struck_forever BOOLEAN column to tasks table."""
        migrations_applied = []
        try:
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]

            if "struck_forever" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN struck_forever BOOLEAN DEFAULT 0")
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
        """Migration 11: Add analytics history tables for strike calendar and daily recap."""
        migrations_applied = []
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS strike_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    day TEXT NOT NULL,
                    strike_type TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_strike_events_user_day ON strike_events (user_id, day)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_strike_events_user_task ON strike_events (user_id, task_id, created_at)"
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings_change_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    day TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_settings_change_events_user_day ON settings_change_events (user_id, day)"
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS recap_seen (
                    user_id TEXT NOT NULL,
                    recap_day TEXT NOT NULL,
                    seen_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, recap_day),
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """
            )

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
        """Migration 12: Add refreshed_at column to tasks table for daily reset badge."""
        migrations_applied = []
        try:
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
                self.logger.info("refreshed_at column already exists, skipping migration 012")

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 012 failed: {e}")
            raise

    def _migration_013_last_daily_reset_at(self, conn) -> List[Dict[str, Any]]:
        """Migration 13: Add last_daily_reset_at to user settings."""
        migrations_applied = []
        try:
            cursor = conn.execute("PRAGMA table_info(settings)")
            columns = [row[1] for row in cursor.fetchall()]

            if "last_daily_reset_at" not in columns:
                conn.execute("ALTER TABLE settings ADD COLUMN last_daily_reset_at TEXT")
                self.logger.info("Added last_daily_reset_at column to settings table")

                migrations_applied.append(
                    {
                        "version": 13,
                        "description": "Added last_daily_reset_at column to settings table",
                        "sql": "ALTER TABLE settings ADD COLUMN last_daily_reset_at TEXT",
                    }
                )

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 013 failed: {e}")
            raise

    def _migration_014_mobile_inbox(self, conn) -> List[Dict[str, Any]]:
        """Migration 14: Add mobile inbox tables."""
        migrations_applied = []
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mobile_inbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    task_json TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    processed_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mobile_inbox_user_status ON mobile_inbox (user_id, status)"
            )

            self.logger.info("Created mobile_inbox table")
            migrations_applied.append(
                {
                    "version": 14,
                    "description": "Created mobile_inbox table",
                    "sql": "CREATE TABLE mobile_inbox",
                }
            )

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 014 failed: {e}")
            raise

    def _migration_015_settings_events(self, conn) -> List[Dict[str, Any]]:
        """Migration 15: Add settings_events table for streak tracking."""
        migrations_applied = []
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settings_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    day TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_settings_events_user_day ON settings_events (user_id, day)"
            )

            self.logger.info("Created settings_events table")
            migrations_applied.append(
                {
                    "version": 15,
                    "description": "Created settings_events table",
                    "sql": "CREATE TABLE settings_events",
                }
            )

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 015 failed: {e}")
            raise

    def _migration_016_deleted_tasks(self, conn) -> List[Dict[str, Any]]:
        """Migration 16: Add deleted_tasks table."""
        migrations_applied = []
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS deleted_tasks (
                    user_id TEXT NOT NULL,
                    task_id TEXT NOT NULL,
                    task_json TEXT NOT NULL,
                    deleted_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, task_id),
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_deleted_tasks_user ON deleted_tasks (user_id)"
            )

            self.logger.info("Created deleted_tasks table")
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
        """Migration 17: Add daily_reset_count column."""
        migrations_applied = []
        try:
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
                        "description": "Added daily_reset_count column to settings table",
                        "sql": "ALTER TABLE settings ADD COLUMN daily_reset_count INTEGER DEFAULT 0",
                    }
                )

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 017 failed: {e}")
            raise

    def _migration_018_notes_folders(self, conn) -> List[Dict[str, Any]]:
        """Migration 18: Add folder support for notes."""
        migrations_applied = []
        try:
            cursor = conn.execute("PRAGMA table_info(notes)")
            columns = [row[1] for row in cursor.fetchall()]

            if "folder_id" not in columns:
                conn.execute("ALTER TABLE notes ADD COLUMN folder_id TEXT")
                self.logger.info("Added folder_id column to notes table")

                migrations_applied.append(
                    {
                        "version": 18,
                        "description": "Added folder_id column to notes table",
                        "sql": "ALTER TABLE notes ADD COLUMN folder_id TEXT",
                    }
                )

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 018 failed: {e}")
            raise

    def _migration_019_daily_reset_log(self, conn) -> List[Dict[str, Any]]:
        """Migration 19: Create daily_reset_log table for daily reset summaries."""
        migrations_applied = []
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_reset_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    reset_date TEXT NOT NULL,
                    tasks_reset INTEGER DEFAULT 0,
                    tasks_struck INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
                    UNIQUE(user_id, reset_date)
                )
            """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_daily_reset_log_user_date ON daily_reset_log (user_id, reset_date)"
            )

            self.logger.info("Created daily_reset_log table")
            migrations_applied.append(
                {
                    "version": 19,
                    "description": "Created daily_reset_log table",
                    "sql": "CREATE TABLE daily_reset_log",
                }
            )

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 019 failed: {e}")
            raise

    def _migration_020_tasks_recurrence_snooze(self, conn) -> List[Dict[str, Any]]:
        """Migration 20: Add recurrence/snooze fields to tasks."""
        migrations_applied = []
        try:
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]

            if "recurrence_type" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN recurrence_type TEXT")
                self.logger.info("Added recurrence_type column to tasks table")

                migrations_applied.append(
                    {
                        "version": 20,
                        "name": "add_recurrence_type",
                        "description": "Added recurrence_type column to tasks table",
                    }
                )

            if "recurrence_param" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN recurrence_param TEXT")
                self.logger.info("Added recurrence_param column to tasks table")

                migrations_applied.append(
                    {
                        "version": 20,
                        "name": "add_recurrence_param",
                        "description": "Added recurrence_param column to tasks table",
                    }
                )

            if "snoozed_until" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN snoozed_until TIMESTAMP")
                self.logger.info("Added snoozed_until column to tasks table")

                migrations_applied.append(
                    {
                        "version": 20,
                        "name": "add_snoozed_until",
                        "description": "Added snoozed_until column to tasks table",
                    }
                )

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 020 failed: {e}")
            raise

    def _migration_021_notes_pin_archive(self, conn) -> List[Dict[str, Any]]:
        """Migration 21: Add pinned/archived flags to notes."""
        migrations_applied = []
        try:
            cursor = conn.execute("PRAGMA table_info(notes)")
            columns = [row[1] for row in cursor.fetchall()]

            if "pinned" not in columns:
                conn.execute("ALTER TABLE notes ADD COLUMN pinned BOOLEAN DEFAULT 0")
                self.logger.info("Added pinned column to notes table")

                migrations_applied.append(
                    {
                        "version": 21,
                        "name": "add_pinned",
                        "description": "Added pinned column to notes table",
                    }
                )

            if "archived" not in columns:
                conn.execute("ALTER TABLE notes ADD COLUMN archived BOOLEAN DEFAULT 0")
                self.logger.info("Added archived column to notes table")

                migrations_applied.append(
                    {
                        "version": 21,
                        "name": "add_archived",
                        "description": "Added archived column to notes table",
                    }
                )

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 021 failed: {e}")
            raise

    def _migration_022_daily_recap_feedback(self, conn) -> List[Dict[str, Any]]:
        """Migration 22: Add daily_recap_feedback table."""
        migrations_applied = []
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_recap_feedback (
                    user_id TEXT NOT NULL,
                    recap_day TEXT NOT NULL,
                    feedback_type TEXT,
                    notes TEXT,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, recap_day),
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_daily_recap_feedback_user ON daily_recap_feedback (user_id)"
            )

            self.logger.info("Created daily_recap_feedback table")
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
        """Migration 23: Add compact_mode setting."""
        migrations_applied = []
        try:
            cursor = conn.execute("PRAGMA table_info(settings)")
            columns = [row[1] for row in cursor.fetchall()]

            if "compact_mode" not in columns:
                conn.execute("ALTER TABLE settings ADD COLUMN compact_mode BOOLEAN DEFAULT 0")
                self.logger.info("Added compact_mode column to settings table")

                migrations_applied.append(
                    {
                        "version": 23,
                        "description": "Added compact_mode column to settings table",
                        "sql": "ALTER TABLE settings ADD COLUMN compact_mode BOOLEAN DEFAULT 0",
                    }
                )

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 023 failed: {e}")
            raise

    def _migration_024_notes_trash_versions_subtasks(self, conn) -> List[Dict[str, Any]]:
        """Migration 24: Notes trash, version history, task subtasks."""
        migrations_applied = []
        try:
            # Add trash support for notes
            cursor = conn.execute("PRAGMA table_info(notes)")
            columns = [row[1] for row in cursor.fetchall()]

            if "deleted" not in columns:
                conn.execute("ALTER TABLE notes ADD COLUMN deleted BOOLEAN DEFAULT 0")
                self.logger.info("Added deleted column to notes table")

            # Create note_versions table for version history
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS note_versions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    note_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    content TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_note_versions_note_id ON note_versions (note_id)"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_note_versions_user_id ON note_versions (user_id)"
            )

            # Add subtasks to tasks table
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]

            if "subtasks" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN subtasks TEXT")
                self.logger.info("Added subtasks column to tasks table")

            self.logger.info("Created note_versions table")
            migrations_applied.append(
                {
                    "version": 24,
                    "description": "Added notes trash/deleted column, created note_versions table, added subtasks column",
                    "sql": "ALTER TABLE notes/tasks ADD COLUMN, CREATE TABLE note_versions",
                }
            )

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 024 failed: {e}")
            raise

    def _migration_025_owner_column(self, conn) -> List[Dict[str, Any]]:
        """Migration 25: Add owner column to tasks."""
        migrations_applied = []
        try:
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]

            if "owner" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN owner TEXT")
                self.logger.info("Added owner column to tasks table")

                migrations_applied.append(
                    {
                        "version": 25,
                        "description": "Added owner column to tasks table",
                        "sql": "ALTER TABLE tasks ADD COLUMN owner TEXT",
                    }
                )

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 025 failed: {e}")
            raise

    def _migration_026_mobile_sync_requests(self, conn) -> List[Dict[str, Any]]:
        """Migration 26: Add mobile_sync_requests table and sequence_num to mobile_inbox."""
        migrations_applied = []
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS mobile_sync_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    request_type TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
                )
            """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_mobile_sync_requests_user_status ON mobile_sync_requests (user_id, status)"
            )

            cursor = conn.execute("PRAGMA table_info(mobile_inbox)")
            columns = [row[1] for row in cursor.fetchall()]

            if "sequence_num" not in columns:
                conn.execute("ALTER TABLE mobile_inbox ADD COLUMN sequence_num INTEGER")
                self.logger.info("Added sequence_num column to mobile_inbox table")

            self.logger.info("Created mobile_sync_requests table")
            migrations_applied.append(
                {
                    "version": 26,
                    "description": "Created mobile_sync_requests table and added sequence_num to mobile_inbox",
                    "sql": "CREATE TABLE mobile_sync_requests, ALTER TABLE mobile_inbox",
                }
            )

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 026 failed: {e}")
            raise

    def _migration_027_add_missing_indexes(self, conn) -> List[Dict[str, Any]]:
        """Migration 27: Add missing indexes for common queries."""
        migrations_applied = []
        try:
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
        """Migration 28: Add parent_id column to tasks table for nesting/subtasks support."""
        migrations_applied: List[Dict[str, Any]] = []
        try:
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]

            if "parent_id" not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN parent_id TEXT")
                self.logger.info("Added parent_id column to tasks table")

                # Create index for parent_id lookups
                conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_parent_id ON tasks (parent_id)")
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
        """Migration 29: Add parent_id column to notes table for nesting/hierarchy support."""
        migrations_applied: List[Dict[str, Any]] = []
        try:
            cursor = conn.execute("PRAGMA table_info(notes)")
            columns = [row[1] for row in cursor.fetchall()]

            if "parent_id" not in columns:
                conn.execute("ALTER TABLE notes ADD COLUMN parent_id TEXT")
                self.logger.info("Added parent_id column to notes table")

                # Create index for parent_id lookups
                conn.execute("CREATE INDEX IF NOT EXISTS idx_notes_parent_id ON notes (parent_id)")
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
        """Migration 30: Create archived_tasks table for task archival system."""
        migrations_applied: List[Dict[str, Any]] = []
        try:
            # Check if archived_tasks table already exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='archived_tasks'"
            )
            if not cursor.fetchone():
                # Create archived_tasks table with identical schema to tasks plus archived_at
                conn.execute(
                    """
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
                """
                )
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
                self.logger.info("Created composite index on archived_tasks (user_id, archived_at)")

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

    def _migration_031_split_content_tracking(self, conn) -> List[Dict[str, Any]]:
        """Migration 31: Add split content status tracking to tasks and notes.

        Adds was_split_encoded column to track whether content was originally saved
        using split editor, allowing us to preserve and restore split structure.
        """
        migrations_applied: List[Dict[str, Any]] = []
        try:
            # Add was_split_encoded to tasks table
            cursor = conn.execute("PRAGMA table_info(tasks)")
            task_columns = [row[1] for row in cursor.fetchall()]

            if "was_split_encoded" not in task_columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN was_split_encoded BOOLEAN DEFAULT 0")
                self.logger.info("Added was_split_encoded column to tasks table")

            # Add was_split_encoded to notes table
            cursor = conn.execute("PRAGMA table_info(notes)")
            notes_columns = [row[1] for row in cursor.fetchall()]

            if "was_split_encoded" not in notes_columns:
                conn.execute("ALTER TABLE notes ADD COLUMN was_split_encoded BOOLEAN DEFAULT 0")
                self.logger.info("Added was_split_encoded column to notes table")

            # Add was_split_encoded to archived_tasks table
            cursor = conn.execute("PRAGMA table_info(archived_tasks)")
            archived_columns = [row[1] for row in cursor.fetchall()]

            if "was_split_encoded" not in archived_columns:
                conn.execute(
                    "ALTER TABLE archived_tasks ADD COLUMN was_split_encoded BOOLEAN DEFAULT 0"
                )
                self.logger.info("Added was_split_encoded column to archived_tasks table")

            migrations_applied.append(
                {
                    "version": 31,
                    "description": "Added split content tracking columns to tasks, notes, and archived_tasks",
                    "sql": "ALTER TABLE tasks/notes/archived_tasks ADD COLUMN was_split_encoded BOOLEAN DEFAULT 0",
                }
            )
            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 031 failed: {e}")
            raise

    def _migration_032_decode_split_content(self, conn) -> List[Dict[str, Any]]:
        """Migration 32: Decode existing split-encoded content in tasks and notes.

        Converts all __SHAKSHUKA_SPLIT_B64_V1__ encoded descriptions and content
        to combined plain text and sets was_split_encoded flag.
        """
        from src.utils.content_decoder import decode_split_b64_v1

        migrations_applied: List[Dict[str, Any]] = []
        try:
            # Process tasks table
            cursor = conn.execute(
                "SELECT id, description FROM tasks WHERE description LIKE '__SHAKSHUKA_SPLIT_B64_V1__%'"
            )
            tasks_to_update = cursor.fetchall()

            updated_count = 0
            for task_row in tasks_to_update:
                task_id = task_row[0]
                encoded_desc = task_row[1]

                decoded_data = decode_split_b64_v1(encoded_desc)
                if decoded_data:
                    primary = decoded_data.get("primary", "")
                    secondary = decoded_data.get("secondary", "")
                    combined = primary
                    if secondary.strip():
                        combined = f"{primary}\n\n--- Split Editor ---\n\n{secondary}"

                    conn.execute(
                        "UPDATE tasks SET description = ?, was_split_encoded = 1 WHERE id = ?",
                        (combined, task_id),
                    )
                    updated_count += 1

            if updated_count > 0:
                self.logger.info(f"Decoded {updated_count} split-encoded task descriptions")

            # Process notes table
            cursor = conn.execute(
                "SELECT id, content FROM notes WHERE content LIKE '__SHAKSHUKA_SPLIT_B64_V1__%'"
            )
            notes_to_update = cursor.fetchall()

            notes_updated = 0
            for note_row in notes_to_update:
                note_id = note_row[0]
                encoded_content = note_row[1]

                decoded_data = decode_split_b64_v1(encoded_content)
                if decoded_data:
                    primary = decoded_data.get("primary", "")
                    secondary = decoded_data.get("secondary", "")
                    combined = primary
                    if secondary.strip():
                        combined = f"{primary}\n\n--- Split Editor ---\n\n{secondary}"

                    conn.execute(
                        "UPDATE notes SET content = ?, was_split_encoded = 1 WHERE id = ?",
                        (combined, note_id),
                    )
                    notes_updated += 1

            if notes_updated > 0:
                self.logger.info(f"Decoded {notes_updated} split-encoded note contents")

            # Process archived_tasks table
            cursor = conn.execute(
                "SELECT id, description FROM archived_tasks WHERE description LIKE '__SHAKSHUKA_SPLIT_B64_V1__%'"
            )
            archived_to_update = cursor.fetchall()

            archived_updated = 0
            for archived_row in archived_to_update:
                archived_id = archived_row[0]
                encoded_desc = archived_row[1]

                decoded_data = decode_split_b64_v1(encoded_desc)
                if decoded_data:
                    primary = decoded_data.get("primary", "")
                    secondary = decoded_data.get("secondary", "")
                    combined = primary
                    if secondary.strip():
                        combined = f"{primary}\n\n--- Split Editor ---\n\n{secondary}"

                    conn.execute(
                        "UPDATE archived_tasks SET description = ?, was_split_encoded = 1 WHERE id = ?",
                        (combined, archived_id),
                    )
                    archived_updated += 1

            if archived_updated > 0:
                self.logger.info(f"Decoded {archived_updated} split-encoded archived task descriptions")

            migrations_applied.append(
                {
                    "version": 32,
                    "description": "Decoded split-encoded content in tasks, notes, and archived_tasks",
                    "sql": "UPDATE tasks/notes/archived_tasks SET ... was_split_encoded = 1",
                }
            )

            total_decoded = updated_count + notes_updated + archived_updated
            if total_decoded > 0:
                self.logger.info(f"Migration 032 completed: Decoded {total_decoded} split-encoded records")

            return migrations_applied
        except Exception as e:
            self.logger.error(f"Migration 032 failed: {e}")
            raise
