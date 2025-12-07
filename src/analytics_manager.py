"""Centralized analytics storage using SQLite only.

This module replaces the previous JSON-based analytics.json file
and provides a tiny SQLite-backed store for analytics counters.

Data is stored in %APPDATA%/Shakshuka/analytics.db on Windows
(via src.utils.paths.get_user_data_dir) so it survives application
reinstalls and works in both dev and frozen modes.
"""

from __future__ import annotations

import os
import sqlite3
import json
from datetime import datetime, date
from typing import Dict, Any

from src.utils.paths import get_user_data_dir

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
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )

    cur = conn.execute("SELECT COUNT(*) AS c FROM analytics")
    count = cur.fetchone()[0]
    if count == 0:
        today = date.today().isoformat()
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO analytics (id, today_date, today_strikes, total_strikes, created_at, updated_at) "
            "VALUES (1, ?, 0, 0, ?, ?)",
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
    except Exception:
        # If JSON is invalid, keep existing DB values
        return

    today = str(data.get("today_date") or row["today_date"] or date.today().isoformat())
    try:
        today_strikes = int(data.get("today_strikes", row["today_strikes"] or 0))
    except Exception:
        today_strikes = int(row["today_strikes"] or 0)
    try:
        total_strikes = int(data.get("total_strikes", row["total_strikes"] or 0))
    except Exception:
        total_strikes = int(row["total_strikes"] or 0)

    now = datetime.utcnow().isoformat()
    conn.execute(
        "UPDATE analytics SET today_date = ?, today_strikes = ?, total_strikes = ?, updated_at = ? WHERE id = 1",
        (today, today_strikes, total_strikes, now),
    )
    conn.commit()

    # Try to rename the legacy file so we don't re-migrate on every call
    try:
        os.rename(json_path, json_path + ".bak")
    except Exception:
        # Best-effort only
        pass


def init_analytics_db() -> None:
    """Public helper to initialize the analytics DB and migrate JSON once."""
    with _get_connection() as conn:
        _ensure_schema(conn)
        _maybe_migrate_from_json(conn)


def get_analytics_counters() -> Dict[str, Any]:
    """Return current analytics counters from SQLite.

    Returns a dict with keys: today_date, today_strikes, total_strikes.
    Always safe to call; it will create the DB/row if needed.
    """
    with _get_connection() as conn:
        _ensure_schema(conn)
        _maybe_migrate_from_json(conn)
        cur = conn.execute(
            "SELECT today_date, today_strikes, total_strikes FROM analytics WHERE id = 1"
        )
        row = cur.fetchone()
        if not row:
            today = date.today().isoformat()
            return {"today_date": today, "today_strikes": 0, "total_strikes": 0}

        return {
            "today_date": row["today_date"],
            "today_strikes": int(row["today_strikes"] or 0),
            "total_strikes": int(row["total_strikes"] or 0),
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
        now = datetime.utcnow().isoformat()

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
