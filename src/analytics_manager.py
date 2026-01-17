"""Centralized analytics storage using SQLite only.

This module replaces the previous JSON-based analytics.json file
and provides a tiny SQLite-backed store for analytics counters.

Data is stored in %APPDATA%/Shakshuka/analytics.db on Windows
(via src.utils.paths.get_user_data_dir) so it survives application
reinstalls and works in both dev and frozen modes.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import json
from datetime import datetime, date
from typing import Dict, Any

from src.utils.paths import get_user_data_dir

logger = logging.getLogger(__name__)

# Valid counter names for increment/decrement operations
_VALID_COUNTERS = frozenset(['tasks_deleted', 'tasks_edited', 'tasks_with_dates', 'tasks_with_time', 'tasks_planned'])

_DB_FILENAME = "analytics.db"
_JSON_FILENAME = "analytics.json"  # legacy file for one-time migration


def _get_db_path() -> str:
    """Return full path to the analytics SQLite database."""
    return os.path.join(get_user_data_dir(), _DB_FILENAME)


def _get_connection() -> sqlite3.Connection:
    """Open a connection to the analytics database with basic config."""
    db_path = _get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Ensure the analytics table exists and has a single row (id=1)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS analytics (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            today_date TEXT NOT NULL,
            today_strikes INTEGER NOT NULL DEFAULT 0,
            total_strikes INTEGER NOT NULL DEFAULT 0,
            tasks_deleted INTEGER NOT NULL DEFAULT 0,
            tasks_edited INTEGER NOT NULL DEFAULT 0,
            tasks_with_dates INTEGER NOT NULL DEFAULT 0,
            tasks_with_time INTEGER NOT NULL DEFAULT 0,
            tasks_planned INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    # Add new columns if they don't exist (for migration)
    # OperationalError with "duplicate column" is expected if column exists
    for col in ('tasks_deleted', 'tasks_edited', 'tasks_with_dates', 'tasks_with_time', 'tasks_planned'):
        try:
            conn.execute(f"ALTER TABLE analytics ADD COLUMN {col} INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError as e:
            if 'duplicate column' not in str(e).lower():
                logger.warning("analytics schema migration warning for %s: %s", col, e)

    cur = conn.execute("SELECT COUNT(*) AS c FROM analytics")
    count = cur.fetchone()[0]
    if count == 0:
        today = date.today().isoformat()
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT INTO analytics (id, today_date, today_strikes, total_strikes, tasks_deleted, tasks_edited, tasks_with_dates, tasks_with_time, tasks_planned, created_at, updated_at) "
            "VALUES (1, ?, 0, 0, 0, 0, 0, 0, 0, ?, ?)",
            (today, now, now),
        )
        conn.commit()


def _maybe_migrate_from_json(conn: sqlite3.Connection) -> None:
    """One-time migration from legacy analytics.json into SQLite.

    If analytics.json exists and the DB row still has default-ish values,
    merge the JSON values into the DB and rename the JSON file to .bak.
    """
    user_dir = get_user_data_dir()
    json_path = os.path.join(user_dir, _JSON_FILENAME)
    if not os.path.exists(json_path):
        return

    # Read current DB row
    cur = conn.execute(
        "SELECT today_date, today_strikes, total_strikes FROM analytics WHERE id = 1"
    )
    row = cur.fetchone()
    if not row:
        return

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
    except (OSError, json.JSONDecodeError) as e:
        # If JSON is invalid or unreadable, keep existing DB values
        logger.warning("analytics JSON migration skipped (invalid file): %s", e)
        return

    today = str(data.get("today_date") or row["today_date"] or date.today().isoformat())
    try:
        today_strikes = int(data.get("today_strikes", row["today_strikes"] or 0))
    except (ValueError, TypeError) as e:
        logger.warning("analytics JSON migration: invalid today_strikes value, using DB fallback: %s", e)
        today_strikes = int(row["today_strikes"] or 0)
    try:
        total_strikes = int(data.get("total_strikes", row["total_strikes"] or 0))
    except (ValueError, TypeError) as e:
        logger.warning("analytics JSON migration: invalid total_strikes value, using DB fallback: %s", e)
        total_strikes = int(row["total_strikes"] or 0)

    now = datetime.now().isoformat()
    conn.execute(
        "UPDATE analytics SET today_date = ?, today_strikes = ?, total_strikes = ?, updated_at = ? WHERE id = 1",
        (today, today_strikes, total_strikes, now),
    )
    conn.commit()

    # Try to rename the legacy file so we don't re-migrate on every call
    try:
        os.rename(json_path, json_path + ".bak")
    except OSError as e:
        # Best-effort only, but log for visibility
        logger.debug("analytics JSON backup rename failed: %s", e)


def init_analytics_db() -> None:
    """Public helper to initialize the analytics DB and migrate JSON once."""
    with _get_connection() as conn:
        _ensure_schema(conn)
        _maybe_migrate_from_json(conn)


def get_analytics_counters() -> Dict[str, Any]:
    """Return current analytics counters from SQLite.

    Returns a dict with keys: today_date, today_strikes, total_strikes, and new counters.
    Always safe to call; it will create the DB/row if needed.
    """
    with _get_connection() as conn:
        _ensure_schema(conn)
        _maybe_migrate_from_json(conn)
        cur = conn.execute(
            "SELECT today_date, today_strikes, total_strikes, tasks_deleted, tasks_edited, tasks_with_dates, tasks_with_time, tasks_planned FROM analytics WHERE id = 1"
        )
        row = cur.fetchone()
        if not row:
            today = date.today().isoformat()
            return {
                "today_date": today, "today_strikes": 0, "total_strikes": 0,
                "tasks_deleted": 0, "tasks_edited": 0, "tasks_with_dates": 0,
                "tasks_with_time": 0, "tasks_planned": 0
            }

        today = date.today().isoformat()
        stored_today = str(row["today_date"] or today)
        today_strikes = int(row["today_strikes"] or 0)
        total_strikes = int(row["total_strikes"] or 0)
        tasks_deleted = int(row["tasks_deleted"] or 0)
        tasks_edited = int(row["tasks_edited"] or 0)
        tasks_with_dates = int(row["tasks_with_dates"] or 0)
        tasks_with_time = int(row["tasks_with_time"] or 0)
        tasks_planned = int(row["tasks_planned"] or 0)

        # Roll over on read so UI shows 0 for a new day even before the first strike.
        if stored_today != today:
            stored_today = today
            today_strikes = 0
            now = datetime.now().isoformat()
            try:
                conn.execute(
                    "UPDATE analytics SET today_date = ?, today_strikes = ?, updated_at = ? WHERE id = 1",
                    (stored_today, today_strikes, now),
                )
                conn.commit()
            except sqlite3.Error as e:
                # Log but don't break user flow - read still returns correct data
                logger.warning("analytics day rollover write failed: %s", e)

        return {
            "today_date": stored_today,
            "today_strikes": today_strikes,
            "total_strikes": total_strikes,
            "tasks_deleted": tasks_deleted,
            "tasks_edited": tasks_edited,
            "tasks_with_dates": tasks_with_dates,
            "tasks_with_time": tasks_with_time,
            "tasks_planned": tasks_planned,
        }


def increment_strike_counter() -> None:
    """Increment analytics counters for a strike event.

    - Rolls over today_strikes when day changes
    - Always increments total_strikes
    """
    with _get_connection() as conn:
        _ensure_schema(conn)
        _maybe_migrate_from_json(conn)

        today = date.today().isoformat()
        now = datetime.now().isoformat()

        cur = conn.execute(
            "SELECT today_date, today_strikes, total_strikes FROM analytics WHERE id = 1"
        )
        row = cur.fetchone()
        if not row:
            current_today = today
            today_strikes = 0
            total_strikes = 0
        else:
            current_today = row["today_date"] or today
            today_strikes = int(row["today_strikes"] or 0)
            total_strikes = int(row["total_strikes"] or 0)

        # Roll over if stored date is from a previous day
        if current_today != today:
            current_today = today
            today_strikes = 0

        today_strikes += 1
        total_strikes += 1

        conn.execute(
            """
            UPDATE analytics
            SET today_date = ?, today_strikes = ?, total_strikes = ?, updated_at = ?
            WHERE id = 1
            """,
            (current_today, today_strikes, total_strikes, now),
        )
        conn.commit()


def increment_analytics_counter(counter_name: str) -> None:
    """Increment a specific analytics counter by 1.
    
    Valid counter names: tasks_deleted, tasks_edited, tasks_with_dates, tasks_with_time, tasks_planned
    
    Logs warning for invalid counter names but never raises to avoid breaking user flows.
    """
    if not isinstance(counter_name, str):
        logger.warning("increment_analytics_counter: counter_name must be str, got %s", type(counter_name).__name__)
        return
    if counter_name not in _VALID_COUNTERS:
        logger.warning("increment_analytics_counter: invalid counter_name %r", counter_name)
        return
    
    try:
        with _get_connection() as conn:
            _ensure_schema(conn)
            now = datetime.now().isoformat()
            conn.execute(
                f"UPDATE analytics SET {counter_name} = {counter_name} + 1, updated_at = ? WHERE id = 1",
                (now,),
            )
            conn.commit()
    except sqlite3.Error as e:
        # Log but don't break user flow
        logger.warning("increment_analytics_counter failed for %s: %s", counter_name, e)


def decrement_analytics_counter(counter_name: str, amount: int = 1) -> None:
    """Decrement a specific analytics counter.
    
    Logs warning for invalid inputs but never raises to avoid breaking user flows.
    """
    if not isinstance(counter_name, str):
        logger.warning("decrement_analytics_counter: counter_name must be str, got %s", type(counter_name).__name__)
        return
    if counter_name not in _VALID_COUNTERS:
        logger.warning("decrement_analytics_counter: invalid counter_name %r", counter_name)
        return
    try:
        n = int(amount)
    except (TypeError, ValueError) as e:
        logger.warning("decrement_analytics_counter: invalid amount %r, defaulting to 1: %s", amount, e)
        n = 1
    if n <= 0:
        logger.debug("decrement_analytics_counter: amount %d <= 0, skipping", n)
        return

    try:
        with _get_connection() as conn:
            _ensure_schema(conn)
            now = datetime.now().isoformat()
            conn.execute(
                f"UPDATE analytics SET {counter_name} = CASE WHEN {counter_name} - ? < 0 THEN 0 ELSE {counter_name} - ? END, updated_at = ? WHERE id = 1",
                (n, n, now),
            )
            conn.commit()
    except sqlite3.Error as e:
        # Log but don't break user flow
        logger.warning("decrement_analytics_counter failed for %s: %s", counter_name, e)


def reset_analytics_counters() -> None:
    with _get_connection() as conn:
        _ensure_schema(conn)
        _maybe_migrate_from_json(conn)
        today = date.today().isoformat()
        now = datetime.now().isoformat()
        conn.execute(
            """
            UPDATE analytics
            SET today_date = ?,
                today_strikes = 0,
                total_strikes = 0,
                tasks_deleted = 0,
                tasks_edited = 0,
                tasks_with_dates = 0,
                tasks_with_time = 0,
                tasks_planned = 0,
                updated_at = ?
            WHERE id = 1
            """,
            (today, now),
        )
        conn.commit()
