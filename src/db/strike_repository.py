"""
Strike repository for strike recording and analytics operations.
Extracted from sqlite_data_manager.py for modularity and testing.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from src.exceptions import DatabaseError, ValidationError


logger = logging.getLogger(__name__)


class StrikeRepository:
    """
    Repository for strike tracking and analytics.
    Handles strike events, daily reset logs, and activity tracking.
    """

    def __init__(self, get_connection, ensure_user_exists, logger=None):
        """
        Initialize repository with database connection.
        
        Args:
            get_connection: Function to get a database connection
            ensure_user_exists: Function to ensure user exists
            logger: Logger instance (optional)
        """
        self.get_connection = get_connection
        self.ensure_user_exists = ensure_user_exists
        self.logger = logger or globals()["logger"]

    def add_strike_event(
        self, user_id: str, task_id: str, day: str, strike_type: str
    ) -> bool:
        """
        Record a strike event for a task on a specific day.
        
        Args:
            user_id: User ID
            task_id: Task ID
            day: Date in YYYY-MM-DD format
            strike_type: Either 'today' or 'forever'
        """
        try:
            self.ensure_user_exists(user_id)
            if not user_id or not task_id or not day:
                return False
            if strike_type not in ("today", "forever"):
                return False
            
            created_at = datetime.now().isoformat()
            with self.get_connection() as conn:
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

    def load_strike_today_report_history(
        self, user_id: str, task_id: str, limit: int = 100, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Load strike report history for a specific task"""
        try:
            self.ensure_user_exists(user_id)
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

            with self.get_connection() as conn:
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

    def add_settings_change_event(
        self,
        user_id: str,
        setting_key: str = "general",
        old_value: str = None,
        new_value: str = None,
    ) -> bool:
        """
        Record a settings change event for streak tracking.
        
        Used by daily recap/analytics counters and streak calculation.
        """
        try:
            self.ensure_user_exists(user_id)
            with self.get_connection() as conn:
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
            self.ensure_user_exists(user_id)
            with self.get_connection() as conn:
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
            with self.get_connection() as conn:
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
            with self.get_connection() as conn:
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
        """
        Get strike contributions for a specific month (YYYY-MM format).
        
        Returns data about which days had strikes and how many tasks were added.
        """
        try:
            self.ensure_user_exists(user_id)
            if not month or not isinstance(month, str) or len(month) != 7:
                raise ValidationError(message="Invalid month")

            with self.get_connection() as conn:
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
        """List months with strike contributions for a user"""
        try:
            self.ensure_user_exists(user_id)
            limit = int(limit or 24)
            if limit <= 0:
                limit = 24
            if limit > 120:
                limit = 120
            
            with self.get_connection() as conn:
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
        """
        Persist a compact summary of tasks affected by a daily reset.
        
        Keeps only the most recent 30 reset logs per user to prevent unbounded growth.
        """
        try:
            self.ensure_user_exists(user_id)
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

            with self.get_connection() as conn:
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
        """
        Return the latest daily reset log for a user.
        
        Args:
            user_id: User ID
            include_seen: If False, only returns unseen logs
        """
        try:
            self.ensure_user_exists(user_id)
            with self.get_connection() as conn:
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

    def mark_daily_reset_log_seen(self, user_id: str, log_id: str) -> bool:
        """Mark a daily reset log as seen by the user"""
        try:
            self.ensure_user_exists(user_id)
            with self.get_connection() as conn:
                conn.execute("BEGIN IMMEDIATE TRANSACTION")
                conn.execute(
                    """
                    UPDATE daily_reset_log
                    SET seen = 1
                    WHERE user_id = ? AND id = ?
                    """,
                    (user_id, log_id),
                )
                conn.commit()
            return True
        except Exception as e:
            self.logger.exception(
                "Error marking daily reset log %s as seen for user %s", log_id, user_id
            )
            raise DatabaseError(
                message="Error marking daily reset log as seen",
                details={"user_id": user_id, "log_id": log_id},
                cause=e,
            )
