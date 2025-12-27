"""
Analytics-related database queries with type hints.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger(__name__)


def get_task_completion_stats(
    conn: sqlite3.Connection,
    user_id: str,
    days: int = 30
) -> Dict[str, Any]:
    """Get task completion statistics for a user."""
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    cursor = conn.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN completed = 0 THEN 1 ELSE 0 END) as pending
        FROM tasks 
        WHERE user_id = ? AND created_at >= ?
    ''', (user_id, cutoff_date))
    
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
    """Get daily task completion counts for charting."""
    cutoff_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
    
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
        except:
            pass
    
    # Combine all queries with UNION
    combined_query = ' UNION '.join(queries) + ' ORDER BY date DESC'
    
    cursor = conn.execute(combined_query, tuple(params))
    activity_dates = set(row[0] for row in cursor.fetchall())
    
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
    """Get task statistics grouped by project."""
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
    """Get task count by priority level."""
    cursor = conn.execute('''
        SELECT priority, COUNT(*) as count
        FROM tasks 
        WHERE user_id = ? AND completed = 0
        GROUP BY priority
    ''', (user_id,))
    
    return {row[0]: row[1] for row in cursor.fetchall()}


def get_average_completion_time(
    conn: sqlite3.Connection,
    user_id: str,
    days: int = 30
) -> Optional[float]:
    """Get average time to complete tasks (in hours)."""
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    
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
    
    row = cursor.fetchone()
    return round(row[0], 1) if row and row[0] else None


def get_busiest_hours(
    conn: sqlite3.Connection,
    user_id: str,
    limit: int = 5
) -> List[Dict[str, Any]]:
    """Get hours when most tasks are completed."""
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
    
    return [{'hour': row[0], 'count': row[1]} for row in cursor.fetchall()]


def get_weekly_summary(
    conn: sqlite3.Connection,
    user_id: str
) -> Dict[str, Any]:
    """Get summary of task activity for the current week."""
    week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime('%Y-%m-%d')
    
    cursor = conn.execute('''
        SELECT 
            COUNT(*) as created,
            SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed,
            SUM(estimated_duration) as total_duration
        FROM tasks 
        WHERE user_id = ? AND DATE(created_at) >= ?
    ''', (user_id, week_start))
    
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
    """Get strike data for calendar view."""
    start_date = f"{year}-{month:02d}-01"
    if month == 12:
        end_date = f"{year + 1}-01-01"
    else:
        end_date = f"{year}-{month + 1:02d}-01"
    
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
    
    return [{'date': row[0], 'strikes': row[1]} for row in cursor.fetchall()]


def get_overdue_tasks_count(
    conn: sqlite3.Connection,
    user_id: str
) -> int:
    """Count overdue tasks."""
    today = datetime.now().strftime('%Y-%m-%d')
    
    cursor = conn.execute('''
        SELECT COUNT(*) 
        FROM tasks 
        WHERE user_id = ? 
            AND completed = 0 
            AND due_date IS NOT NULL 
            AND DATE(due_date) < ?
    ''', (user_id, today))
    
    return cursor.fetchone()[0]
