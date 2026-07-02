"""
Task repository for CRUD operations on tasks.
Extracted from sqlite_data_manager.py for modularity and testing.
"""

import json
import logging
import sqlite3
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.constants import MAX_RETRIES, RETRY_DELAY_SECONDS
from src.exceptions import DatabaseError, DataManagerException, ValidationError
from src.utils.content_decoder import is_split_encoded, normalize_content


logger = logging.getLogger(__name__)


class TaskRepository:
    """
    Repository for task operations.
    Handles creation, retrieval, updates, and validation of tasks.
    """

    def __init__(self, get_connection, ensure_user_exists, logger=None):
        """
        Initialize repository with database connection and user validation.
        
        Args:
            get_connection: Function to get a database connection
            ensure_user_exists: Function to ensure user exists
            logger: Logger instance (optional, uses module logger if None)
        """
        self.get_connection = get_connection
        self.ensure_user_exists = ensure_user_exists
        self.logger = logger or globals()["logger"]
        self._lock_factory = None

    def create_task(
        self, user_id: str, task_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Create a single task for a user with transaction safety and duplicate checking.

        This method enforces a per-user duplicate check on (title, project)
        for active (non-completed) tasks, unless the caller explicitly passes
        ignore_duplicate=True in the task_data payload.
        """
        max_retries = MAX_RETRIES
        retry_delay = RETRY_DELAY_SECONDS

        for attempt in range(max_retries):
            try:
                self.ensure_user_exists(user_id)

                if task_data is None or not isinstance(task_data, dict):
                    return None

                # Optional flag - not persisted to DB
                ignore_duplicate = bool(task_data.pop("ignore_duplicate", False))

                if "id" not in task_data:
                    task_data["id"] = str(uuid.uuid4())

                task_data = self._normalize_task_dict(task_data)

                if not self._validate_task(task_data):
                    self.logger.error(f"Task validation failed for user {user_id}")
                    return None

                with self.get_connection() as conn:
                    conn.execute("BEGIN IMMEDIATE TRANSACTION")

                    try:
                        # Duplicate guard
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
                                        "Duplicate task detected for user %s (title=%r, project=%r)",
                                        user_id,
                                        title,
                                        project_raw,
                                    )
                                    conn.rollback()
                                    raise ValidationError(
                                        message="A similar task already exists",
                                        details={"title": title, "project": project_raw}
                                    )

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
        """Get a specific task by ID"""
        try:
            with self.get_connection() as conn:
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

    def get_active_tasks_for_user(
        self, user_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Load only active (non-completed) tasks for a specific user"""
        try:
            self.ensure_user_exists(user_id)

            with self.get_connection() as conn:
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
                                    "Invalid active task data found for user %s",
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

    def update_task(
        self, user_id: str, task_id: str, task_data: Dict[str, Any]
    ) -> bool:
        """Update a specific task for a user with transaction safety"""
        max_retries = MAX_RETRIES
        retry_delay = RETRY_DELAY_SECONDS

        for attempt in range(max_retries):
            try:
                with self.get_connection() as conn:
                    conn.execute("BEGIN IMMEDIATE TRANSACTION")

                    backup_row = None
                    try:
                        # Get full task and check existence
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
                                json.dumps(merged_task.get("subtasks", [])),
                                datetime.now().isoformat(),
                                task_id,
                                user_id,
                            ),
                        )

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

    def bulk_create_tasks(self, user_id: str, tasks: List[Dict[str, Any]]) -> bool:
        """Bulk create tasks without loading existing tasks"""
        try:
            self.ensure_user_exists(user_id)

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

            with self.get_connection() as conn:
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
                    except Exception:
                        self.logger.exception("Rollback failed during bulk_create_tasks")
                    raise DatabaseError(message="Bulk insert failed", cause=inner_e)

        except Exception as e:
            self.logger.exception("Error bulk creating tasks for user %s", user_id)
            raise DatabaseError(
                message=f"Error bulk creating tasks for user {user_id}", cause=e
            )

    # ---- Helper methods (extracted from original class) ----

    def _validate_task(self, task: Dict[str, Any]) -> bool:
        """Validate task data structure"""
        if task is None or not isinstance(task, dict):
            return False
        if "id" not in task or not task["id"]:
            return False
        if "title" not in task or not task["title"]:
            return False
        return True

    def _normalize_task_dict(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize task dictionary for storage"""
        if task is None or not isinstance(task, dict):
            return {}

        # Ensure all required fields exist with defaults
        normalized = {
            "id": task.get("id") or str(uuid.uuid4()),
            "title": self._sanitize_text(task.get("title"), 500),
            "description": self._sanitize_text(task.get("description"), 10000),
            "project": self._sanitize_text(task.get("project"), 500),
            "owner": self._sanitize_text(task.get("owner"), 500),
            "priority": task.get("priority", "medium"),
            "status": task.get("status", "pending"),
            "completed": bool(task.get("completed", False)),
            "completed_at": task.get("completed_at"),
            "due_date": task.get("due_date"),
            "estimated_duration": int(task.get("estimated_duration", 60)),
            "scheduled_hour": task.get("scheduled_hour"),
            "scheduled_minute": task.get("scheduled_minute"),
            "scheduled_date": task.get("scheduled_date"),
            "scheduled_duration": task.get("scheduled_duration"),
            "struck_forever": bool(task.get("struck_forever", False)),
            "struck_today": bool(task.get("struck_today", False)),
            "struck_date": task.get("struck_date"),
            "strike_report": task.get("strike_report"),
            "strike_count": int(task.get("strike_count", 0)),
            "daily_strikes": task.get("daily_strikes", {}),
            "refreshed_at": task.get("refreshed_at"),
            "recurrence_type": task.get("recurrence_type"),
            "recurrence_param": task.get("recurrence_param"),
            "snoozed_until": task.get("snoozed_until"),
            "subtasks": task.get("subtasks", []),
            "created_at": task.get("created_at", datetime.now().isoformat()),
            "updated_at": task.get("updated_at", datetime.now().isoformat()),
        }

        return normalized

    def _sanitize_text(self, value: Any, max_len: int) -> str:
        """Sanitize and truncate text value"""
        if value is None:
            return ""
        if not isinstance(value, str):
            value = str(value)
        value = value.strip()
        if len(value) > max_len:
            value = value[:max_len]
        return value

    def _task_dict_to_row(self, task: Dict[str, Any], user_id: str) -> tuple:
        """Convert task dict to database row tuple"""
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
            task.get("created_at", datetime.now().isoformat()),
            task.get("updated_at", datetime.now().isoformat()),
        )

    def _row_to_task_dict(self, row: sqlite3.Row) -> Dict[str, Any]:
        """Convert database row to task dict"""
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
