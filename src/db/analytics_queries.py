"""
Analytics-related database queries with type hints.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

from src.exceptions import DatabaseError, ValidationError

logger = logging.getLogger(__name__)


def _validate_conn(conn: sqlite3.Connection, func_name: str) -> None:
    """Validate database connection is provided."""
    if conn is None:
        raise ValidationError(message=f'{func_name}: conn is required')


def _validate_user_id(user_id: str, func_name: str) -> None:
    """Validate user_id is a non-empty string."""
    if not user_id or not isinstance(user_id, str):
        raise ValidationError(message=f'{func_name}: user_id must be a non-empty string')


def _validate_days(days: int, func_name: str) -> int:
    """Validate days parameter and return sanitized value."""
    if not isinstance(days, int) or days < 1:
        raise ValidationError(message=f'{func_name}: days must be a positive integer')
    if days > 365:
        logger.warning("%s: days=%d exceeds 365, capping to 365", func_name, days)
        return 365
    return days


def get_task_completion_stats(
    conn: sqlite3.Connection,
    user_id: str,
    days: int = 30
) -> Dict[str, Any]:
    """Get task completion statistics for a user.
    
    Raises:
        ValidationError: If inputs are invalid.
        DatabaseError: If query fails.
    """
    _validate_conn(conn, 'get_task_completion_stats')
    _validate_user_id(user_id, 'get_task_completion_stats')
    days = _validate_days(days, 'get_task_completion_stats')
    
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    try:
        cursor = conn.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) as pending
        FROM tasks 
        WHERE user_id = ? AND created_at >= ?
    ''', (user_id, cutoff_date))
    except sqlite3.Error as e:
        raise DatabaseError(message='Failed to query task completion stats', cause=e)
    
    row = cursor.fetchone()
    total = row[0] or 0
    completed = row[1] or 0
    pending = row[2] or 0
    
    return {
        'total': total,
        'completed': completed,
        'pending': pending,
        'completion_rate': round(completed / total * 100, 1) if total > 0 else 0
    }


def get_daily_completion_counts(
    conn: sqlite3.Connection,
    user_id: str,
    days: int = 30
) -> List[Dict[str, Any]]:
    """Get daily task completion counts for charting.
    
    Raises:
        ValidationError: If inputs are invalid.
        DatabaseError: If query fails.
    """
    _validate_conn(conn, 'get_daily_completion_counts')
    _validate_user_id(user_id, 'get_daily_completion_counts')
    days = _validate_days(days, 'get_daily_completion_counts')
    
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
    try:
        cursor = conn.execute('''
            SELECT 
                DATE(completed_at) as date,
                COUNT(*) as count
            FROM tasks 
            WHERE user_id = ? 
                AND completed = 1 
                AND DATE(completed_at) >= ?
            GROUP BY DATE(completed_at)
            ORDER BY date
        ''', (user_id, cutoff_date))
    except sqlite3.Error as e:
        raise DatabaseError(message='Failed to query daily completion counts', cause=e)
    
    return [{'date': row[0], 'count': row[1]} for row in cursor.fetchall()]


def get_productivity_streak(
    conn: sqlite3.Connection,
    user_id: str,
    min_tasks: int = 1,
    skip_weekends: bool = False,
    count_new_tasks: bool = False,
    count_settings: bool = False
) -> int:
    """Calculate current productivity streak (consecutive days with activity).
    
    Args:
        conn: Database connection
        user_id: User ID
        min_tasks: Minimum tasks to count as activity (legacy, not used with new options)
        skip_weekends: If True, Saturday and Sunday don't break the streak
        count_new_tasks: If True, adding new tasks counts as activity
        count_settings: If True, settings changes count as activity
    """
    _validate_conn(conn, 'get_productivity_streak')
    _validate_user_id(user_id, 'get_productivity_streak')
    if not isinstance(skip_weekends, bool):
        raise ValidationError(message='get_productivity_streak: skip_weekends must be boolean')
    if not isinstance(count_new_tasks, bool):
        raise ValidationError(message='get_productivity_streak: count_new_tasks must be boolean')
    if not isinstance(count_settings, bool):
        raise ValidationError(message='get_productivity_streak: count_settings must be boolean')

    # Build query to get all activity dates
    queries = []
    params = []
    
    # Always include completed tasks
    queries.append('''
        SELECT DISTINCT DATE(completed_at) as date
        FROM tasks 
        WHERE user_id = ? AND completed = 1 AND completed_at IS NOT NULL
    ''')
    params.append(user_id)
    
    # Optionally include task creation dates
    if count_new_tasks:
        queries.append('''
            SELECT DISTINCT DATE(created_at) as date
            FROM tasks 
            WHERE user_id = ? AND created_at IS NOT NULL
        ''')
        params.append(user_id)
    
    # Optionally include settings change dates
    if count_settings:
        # Check if settings_events table exists
        try:
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings_events'")
            if cursor.fetchone():
                queries.append('''
                    SELECT DISTINCT DATE(timestamp) as date
                    FROM settings_events 
                    WHERE user_id = ?
                ''')
                params.append(user_id)
        except Exception as e:
            raise DatabaseError(message='Failed checking settings_events table', cause=e)
    
    # Combine all queries with UNION
    combined_query = ' UNION '.join(queries) + ' ORDER BY date DESC'
    
    try:
        cursor = conn.execute(combined_query, tuple(params))
        activity_dates = set(row[0] for row in cursor.fetchall())
    except Exception as e:
        raise DatabaseError(message='Failed querying productivity streak activity dates', cause=e)
    
    if not activity_dates:
        return 0
    
    streak = 0
    today = datetime.now().date()
    check_date = today
    
    while True:
        date_str = check_date.strftime('%Y-%m-%d')
        is_weekend = check_date.weekday() >= 5  # Saturday = 5, Sunday = 6
        
        if date_str in activity_dates:
            streak += 1
            check_date -= timedelta(days=1)
        elif skip_weekends and is_weekend:
            # Weekend with no activity - skip it (don't break streak, don't count it)
            check_date -= timedelta(days=1)
        else:
            # No activity and not a skipped weekend - streak is broken
            break
        
        # Safety limit to prevent infinite loops
        if streak > 365:
            break
    
    return streak


def get_project_stats(
    conn: sqlite3.Connection,
    user_id: str
) -> List[Dict[str, Any]]:
    """Get task statistics grouped by project.
    
    Raises:
        ValidationError: If inputs are invalid.
        DatabaseError: If query fails.
    """
    _validate_conn(conn, 'get_project_stats')
    _validate_user_id(user_id, 'get_project_stats')
    
    try:
        cursor = conn.execute('''
        SELECT 
            COALESCE(project, 'No Project') as project,
            COUNT(*) as total,
            SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed
        FROM tasks 
        WHERE user_id = ?
        GROUP BY project
        ORDER BY total DESC
    ''', (user_id,))
    except sqlite3.Error as e:
        raise DatabaseError(message='Failed to query project stats', cause=e)
    
    results = []
    for row in cursor.fetchall():
        total = row[1]
        completed = row[2]
        results.append({
            'project': row[0],
            'total': total,
            'completed': completed,
            'pending': total - completed,
            'completion_rate': round(completed / total * 100, 1) if total > 0 else 0
        })
    
    return results


def get_priority_distribution(
    conn: sqlite3.Connection,
    user_id: str
) -> Dict[str, int]:
    """Get task count by priority level.
    
    Raises:
        ValidationError: If inputs are invalid.
        DatabaseError: If query fails.
    """
    _validate_conn(conn, 'get_priority_distribution')
    _validate_user_id(user_id, 'get_priority_distribution')
    
    try:
        cursor = conn.execute('''
            SELECT priority, COUNT(*) as count
            FROM tasks 
            WHERE user_id = ? AND completed = 0
            GROUP BY priority
        ''', (user_id,))
    except sqlite3.Error as e:
        raise DatabaseError(message='Failed to query priority distribution', cause=e)
    
    return {row[0]: row[1] for row in cursor.fetchall()}


def get_average_completion_time(
    conn: sqlite3.Connection,
    user_id: str,
    days: int = 30
) -> Optional[float]:
    """Get average time to complete tasks (in hours).
    
    Raises:
        ValidationError: If inputs are invalid.
        DatabaseError: If query fails.
    """
    _validate_conn(conn, 'get_average_completion_time')
    _validate_user_id(user_id, 'get_average_completion_time')
    days = _validate_days(days, 'get_average_completion_time')
    
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    try:
        cursor = conn.execute('''
            SELECT AVG(
                (julianday(completed_at) - julianday(created_at)) * 24
            ) as avg_hours
            FROM tasks 
            WHERE user_id = ? 
                AND completed = 1 
                AND completed_at IS NOT NULL
                AND created_at >= ?
        ''', (user_id, cutoff_date))
    except sqlite3.Error as e:
        raise DatabaseError(message='Failed to query average completion time', cause=e)
    
    row = cursor.fetchone()
    return round(row[0], 1) if row and row[0] else None


def get_busiest_hours(
    conn: sqlite3.Connection,
    user_id: str,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """Get hours when most tasks are completed.
    
    Raises:
        ValidationError: If inputs are invalid.
        DatabaseError: If query fails.
    """
    _validate_conn(conn, 'get_busiest_hours')
    _validate_user_id(user_id, 'get_busiest_hours')
    if not isinstance(limit, int) or limit < 1:
        raise ValidationError(message='get_busiest_hours: limit must be a positive integer')
    if limit > 24:
        limit = 24  # Cap at 24 hours
    
    try:
        cursor = conn.execute('''
            SELECT 
                CAST(strftime('%H', completed_at) AS INTEGER) as hour,
                COUNT(*) as count
            FROM tasks 
            WHERE user_id = ? AND completed = 1 AND completed_at IS NOT NULL
            GROUP BY hour
            ORDER BY count DESC
            LIMIT ?
        ''', (user_id, limit))
    except sqlite3.Error as e:
        raise DatabaseError(message='Failed to query busiest hours', cause=e)
    
    return [{'hour': row[0], 'count': row[1]} for row in cursor.fetchall()]


def get_weekly_summary(
    conn: sqlite3.Connection,
    user_id: str
) -> Dict[str, Any]:
    """Get summary of task activity for the current week.
    
    Raises:
        ValidationError: If inputs are invalid.
        DatabaseError: If query fails.
    """
    _validate_conn(conn, 'get_weekly_summary')
    _validate_user_id(user_id, 'get_weekly_summary')
    
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime('%Y-%m-%d')
    
    try:
        cursor = conn.execute('''
            SELECT 
                COUNT(*) as created,
                SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed,
                SUM(estimated_duration) as total_duration
            FROM tasks 
            WHERE user_id = ? AND DATE(created_at) >= ?
        ''', (user_id, week_start))
    except sqlite3.Error as e:
        raise DatabaseError(message='Failed to query weekly summary', cause=e)
    
    row = cursor.fetchone()
    return {
        'week_start': week_start,
        'tasks_created': row[0] or 0,
        'tasks_completed': row[1] or 0,
        'total_duration_minutes': row[2] or 0
    }


def get_strike_calendar(
    conn: sqlite3.Connection,
    user_id: str,
    year: int,
    month: int
) -> List[Dict[str, Any]]:
    """Get strike data for calendar view.
    
    Raises:
        ValidationError: If inputs are invalid.
        DatabaseError: If query fails.
    """
    _validate_conn(conn, 'get_strike_calendar')
    _validate_user_id(user_id, 'get_strike_calendar')
    if not isinstance(year, int) or year < 1970 or year > 2100:
        raise ValidationError(message='get_strike_calendar: year must be integer between 1970 and 2100')
    if not isinstance(month, int) or month < 1 or month > 12:
        raise ValidationError(message='get_strike_calendar: month must be integer between 1 and 12')
    
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    
    try:
        cursor = conn.execute('''
            SELECT 
                DATE(struck_date) as date,
                COUNT(*) as strike_count
            FROM tasks 
            WHERE user_id = ? 
                AND struck_today = 1 
                AND DATE(struck_date) >= ? 
                AND DATE(struck_date) < ?
            GROUP BY DATE(struck_date)
        ''', (user_id, start_date, end_date))
    except sqlite3.Error as e:
        raise DatabaseError(message='Failed to query strike calendar', cause=e)
    
    return [{'date': row[0], 'strikes': row[1]} for row in cursor.fetchall()]


def get_overdue_tasks_count(
    conn: sqlite3.Connection,
    user_id: str
) -> int:
    """Count overdue tasks.
    
    Raises:
        ValidationError: If inputs are invalid.
        DatabaseError: If query fails.
    """
    _validate_conn(conn, 'get_overdue_tasks_count')
    _validate_user_id(user_id, 'get_overdue_tasks_count')
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    try:
        cursor = conn.execute('''
            SELECT COUNT(*) 
            FROM tasks 
            WHERE user_id = ? 
                AND completed = 0 
                AND due_date IS NOT NULL 
                AND DATE(due_date) < ?
        ''', (user_id, today))
    except sqlite3.Error as e:
        raise DatabaseError(message='Failed to query overdue tasks count', cause=e)
    
    return cursor.fetchone()[0]
