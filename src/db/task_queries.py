"""
Task-related database queries with type hints.
"""

import sqlite3
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from src.constants import TaskStatus, TaskPriority

logger = logging.getLogger(__name__)


def create_task(
    conn: sqlite3.Connection,
    user_id: str,
    title: str,
    description: Optional[str] = None,
    project: Optional[str] = None,
    priority: str = TaskPriority.MEDIUM.value,
    due_date: Optional[str] = None,
    estimated_duration: int = 60
) -> Optional[Dict[str, Any]]:
    """Create a new task for a user."""
    task_id = str(uuid.uuid4())
    now = datetime.now().isoformat()
    
    try:
        conn.execute('''
            INSERT INTO tasks (
                id, user_id, title, description, project, priority,
                status, due_date, estimated_duration, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task_id, user_id, title, description, project, priority,
            TaskStatus.PENDING.value, due_date, estimated_duration, now, now
        ))
        conn.commit()
        
        return get_task_by_id(conn, task_id)
    except Exception as e:
        logger.error("Failed to create task: %s", e)
        conn.rollback()
        return None


def get_task_by_id(conn: sqlite3.Connection, task_id: str) -> Optional[Dict[str, Any]]:
    """Get a task by its ID."""
    cursor = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def get_tasks_for_user(
    conn: sqlite3.Connection,
    user_id: str,
    status: Optional[str] = None,
    completed: Optional[bool] = None,
    project: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Get tasks for a user with optional filters."""
    query = 'SELECT * FROM tasks WHERE user_id = ?'
    params: List[Any] = [user_id]
    
    if status is not None:
        query += ' AND status = ?'
        params.append(status)
    
    if completed is not None:
        query += ' AND completed = ?'
        params.append(1 if completed else 0)
    
    if project is not None:
        query += ' AND project = ?'
        params.append(project)
    
    query += ' ORDER BY created_at DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])
    
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def update_task(
    conn: sqlite3.Connection,
    task_id: str,
    **updates: Any
) -> Optional[Dict[str, Any]]:
    """Update a task with the given fields."""
    if not updates:
        return get_task_by_id(conn, task_id)
    
    updates['updated_at'] = datetime.now().isoformat()
    
    set_clause = ', '.join(f'{key} = ?' for key in updates.keys())
    values = list(updates.values()) + [task_id]
    
    try:
        conn.execute(f'UPDATE tasks SET {set_clause} WHERE id = ?', values)
        conn.commit()
        return get_task_by_id(conn, task_id)
    except Exception as e:
        logger.error("Failed to update task %s: %s", task_id, e)
        conn.rollback()
        return None


def delete_task(conn: sqlite3.Connection, task_id: str) -> bool:
    """Delete a task by its ID."""
    try:
        cursor = conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error("Failed to delete task %s: %s", task_id, e)
        conn.rollback()
        return False


def complete_task(conn: sqlite3.Connection, task_id: str) -> Optional[Dict[str, Any]]:
    """Mark a task as completed."""
    now = datetime.now().isoformat()
    return update_task(
        conn, task_id,
        completed=1,
        completed_at=now,
        status=TaskStatus.COMPLETED.value
    )


def uncomplete_task(conn: sqlite3.Connection, task_id: str) -> Optional[Dict[str, Any]]:
    """Mark a task as not completed."""
    return update_task(
        conn, task_id,
        completed=0,
        completed_at=None,
        status=TaskStatus.PENDING.value
    )


def get_scheduled_tasks(
    conn: sqlite3.Connection,
    user_id: str,
    date: str
) -> List[Dict[str, Any]]:
    """Get scheduled tasks for a user on a specific date."""
    cursor = conn.execute('''
        SELECT * FROM tasks 
        WHERE user_id = ? AND scheduled_date = ?
        ORDER BY scheduled_hour, scheduled_minute
    ''', (user_id, date))
    return [dict(row) for row in cursor.fetchall()]


def get_tasks_by_project(
    conn: sqlite3.Connection,
    user_id: str,
    project: str
) -> List[Dict[str, Any]]:
    """Get all tasks for a user in a specific project."""
    cursor = conn.execute('''
        SELECT * FROM tasks 
        WHERE user_id = ? AND project = ?
        ORDER BY created_at DESC
    ''', (user_id, project))
    return [dict(row) for row in cursor.fetchall()]


def get_user_projects(conn: sqlite3.Connection, user_id: str) -> List[str]:
    """Get all unique projects for a user."""
    cursor = conn.execute('''
        SELECT DISTINCT project FROM tasks 
        WHERE user_id = ? AND project IS NOT NULL AND project != ''
        ORDER BY project
    ''', (user_id,))
    return [row[0] for row in cursor.fetchall()]


def count_tasks(
    conn: sqlite3.Connection,
    user_id: str,
    completed: Optional[bool] = None
) -> int:
    """Count tasks for a user."""
    query = 'SELECT COUNT(*) FROM tasks WHERE user_id = ?'
    params: List[Any] = [user_id]
    
    if completed is not None:
        query += ' AND completed = ?'
        params.append(1 if completed else 0)
    
    cursor = conn.execute(query, params)
    return cursor.fetchone()[0]
