"""
Analytics repository for daily recap and feedback operations.
Extracted from sqlite_data_manager.py for modularity and testing.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from src.exceptions import DatabaseError, ValidationError


logger = logging.getLogger(__name__)


class AnalyticsRepository:
    """
    Repository for daily recap and analytics feedback.
    Handles recap data collection, feedback persistence, and status tracking.
    """

    def __init__(self, get_connection, ensure_user_exists, calculate_streak, logger=None):
        """
        Initialize repository with database connection and helpers.
        
        Args:
            get_connection: Function to get a database connection
            ensure_user_exists: Function to ensure user exists
            calculate_streak: Function to calculate streak days from tasks
            logger: Logger instance (optional)
        """
        self.get_connection = get_connection
        self.ensure_user_exists = ensure_user_exists
        self._calculate_streak = calculate_streak
        self.logger = logger or globals()["logger"]

    def get_daily_recap(self, user_id: str, day: str) -> Dict[str, Any]:
        """
        Build a daily recap for the given day.
        
        Includes strikes, completions, task additions, and other metrics.
        """
        try:
            self.ensure_user_exists(user_id)
            if not day:
                raise ValidationError(message="Invalid day")

            with self.get_connection() as conn:
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

                streak_days = self._calculate_streak(conn, user_id, day)

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
        """
        Persist feedback answers for a given recap day.

        Args:
            user_id: User ID
            recap_day: Date for the recap (YYYY-MM-DD)
            answers: Dict of {question_key: answer_string}
                    e.g., {'went_well': '...', 'improve_tomorrow': '...'}

        Each key/value pair is upserted individually so partial saves are safe.
        Silently ignores empty-string keys or non-string values.
        """
        try:
            self.ensure_user_exists(user_id)
            if not recap_day or not isinstance(answers, dict) or not answers:
                return False
            
            now = datetime.now().isoformat()
            with self.get_connection() as conn:
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
        """
        Return previously saved feedback answers for a given recap day.

        Returns a dict {question_key: answer}; empty dict if nothing saved.
        """
        try:
            self.ensure_user_exists(user_id)
            if not recap_day:
                return {}
            
            with self.get_connection() as conn:
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

    def was_recap_seen(self, user_id: str, recap_day: str) -> bool:
        """Check if a recap has been seen by the user"""
        try:
            self.ensure_user_exists(user_id)
            if not recap_day:
                return False
            
            with self.get_connection() as conn:
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
        """Mark a recap as seen by the user"""
        try:
            self.ensure_user_exists(user_id)
            if not recap_day:
                return False
            
            with self.get_connection() as conn:
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

    def get_latest_notes_cleaner_status(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Return a compact status object for the most recent notes-cleaner run.

        This is persisted in the daily_reset_log table using a synthetic
        reset_reason of 'notes_cleaner' and a small payload summarizing the run
        in tasks_json.
        """
        try:
            self.ensure_user_exists(user_id)
            with self.get_connection() as conn:
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
