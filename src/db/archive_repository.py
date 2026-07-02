"""
Archive repository for task archival and deletion operations.
Extracted from sqlite_data_manager.py for modularity and testing.
"""

import json
import logging
import sqlite3
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.constants import MAX_RETRIES, RETRY_DELAY_SECONDS
from src.exceptions import DatabaseError


logger = logging.getLogger(__name__)


class ArchiveRepository:
    """
    Repository for task archival and deletion operations.
    Handles moving completed tasks to archive and permanent deletion.
    """

    def __init__(self, get_connection, ensure_user_exists, row_converters, logger=None):
        """
        Initialize repository with database connection and converters.
        
        Args:
            get_connection: Function to get a database connection
            ensure_user_exists: Function to ensure user exists
            row_converters: Dict with _row_to_task_dict and _task_dict_to_row functions
            logger: Logger instance (optional)
        """
        self.get_connection = get_connection
        self.ensure_user_exists = ensure_user_exists
        self._row_to_task_dict = row_converters["_row_to_task_dict"]
        self._task_dict_to_row = row_converters["_task_dict_to_row"]
        self.logger = logger or globals()["logger"]

    def archive_task(self, user_id: str, task_id: str) -> bool:
        """
        Archive a completed task - move it from tasks to archived_tasks table.
        
        This is typically called after a task is marked as completed.
        """
        max_retries = MAX_RETRIES
        retry_delay = RETRY_DELAY_SECONDS

        for attempt in range(max_retries):
            try:
                with self.get_connection() as conn:
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
                            f"Transaction failed for user {user_id}, task {task_id}, attempt {attempt + 1}: {inner_e}"
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

    def delete_task(self, user_id: str, task_id: str) -> bool:
        """
        Delete a specific task for a user from either active or archived tasks.
        
        This method will attempt to delete from the tasks table first, then from archived_tasks.
        Returns True if the task was found and deleted from either table.
        """
        max_retries = MAX_RETRIES
        retry_delay = RETRY_DELAY_SECONDS

        for attempt in range(max_retries):
            try:
                with self.get_connection() as conn:
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

    def load_archived_tasks_for_user(
        self, user_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Load archived (completed) tasks for a specific user"""
        try:
            self.ensure_user_exists(user_id)

            with self.get_connection() as conn:
                conn.execute("BEGIN")

                try:
                    cursor = conn.execute(
                        """
                        SELECT * FROM archived_tasks
                        WHERE user_id = ?
                        ORDER BY archived_at DESC
                    """,
                        (user_id,),
                    )

                    rows = cursor.fetchall()

                    tasks = []
                    for row in rows:
                        try:
                            task_dict = self._row_to_task_dict(row)
                            tasks.append(task_dict)
                        except Exception as row_e:
                            self.logger.warning(
                                "Failed to convert archived task row for user %s: %s",
                                user_id,
                                row_e,
                            )
                            continue

                    conn.commit()
                    self.logger.info(
                        "Successfully loaded %d archived tasks for user %s",
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
            self.logger.exception("Error loading archived tasks for user %s", user_id)
            raise DatabaseError(
                message=f"Error loading archived tasks for user {user_id}",
                cause=e,
            )

    def restore_task(self, user_id: str, task_id: str) -> bool:
        """
        Restore a task from archived_tasks back to tasks table.
        
        Used when user wants to unarchive a completed task.
        """
        max_retries = MAX_RETRIES
        retry_delay = RETRY_DELAY_SECONDS

        for attempt in range(max_retries):
            try:
                with self.get_connection() as conn:
                    conn.execute("BEGIN IMMEDIATE TRANSACTION")

                    try:
                        # Get the task from archived_tasks table
                        cursor = conn.execute(
                            "SELECT * FROM archived_tasks WHERE id = ? AND user_id = ?",
                            (task_id, user_id),
                        )
                        task_row = cursor.fetchone()

                        if not task_row:
                            self.logger.warning(
                                f"Archived task {task_id} not found for user {user_id}"
                            )
                            conn.rollback()
                            return False

                        # Convert to task dict and prepare for re-insertion to tasks table
                        task_dict = self._row_to_task_dict(task_row)
                        
                        # Reset completion-related fields
                        task_dict["completed"] = False
                        task_dict["completed_at"] = None
                        
                        task_row_tuple = self._task_dict_to_row(task_dict, user_id)

                        # Insert into tasks table
                        conn.execute(
                            """
                            INSERT INTO tasks (
                                id, user_id, title, description, project, owner, priority, status,
                                completed, completed_at, due_date, estimated_duration, scheduled_hour,
                                scheduled_minute, scheduled_date, scheduled_duration, struck_forever, struck_today, struck_date, strike_report, strike_count,
                                daily_strikes, refreshed_at, recurrence_type, recurrence_param, snoozed_until, subtasks, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            task_row_tuple,
                        )

                        # Delete from archived_tasks table
                        conn.execute(
                            "DELETE FROM archived_tasks WHERE id = ? AND user_id = ?",
                            (task_id, user_id),
                        )

                        conn.commit()
                        self.logger.info(
                            f"Successfully restored task {task_id} for user {user_id}"
                        )
                        return True

                    except Exception as inner_e:
                        conn.rollback()
                        self.logger.error(
                            f"Transaction failed for user {user_id}, task {task_id}, attempt {attempt + 1}: {inner_e}"
                        )
                        raise

            except Exception as e:
                self.logger.error(
                    f"Error restoring task {task_id} for user {user_id}, attempt {attempt + 1}: {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (2**attempt))
                    continue
                return False

        return False
