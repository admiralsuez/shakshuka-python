"""
Task-related database queries with type hints.
"""

import sqlite3
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from src.constants import TaskStatus, TaskPriority
from src.exceptions import DatabaseError, ValidationError

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
    if not user_id or not isinstance(user_id, str):
        raise ValidationError(message="Invalid user_id")
    if not title or not isinstance(title, str):
        raise ValidationError(message="Invalid title")
    if not priority or not isinstance(priority, str):
        raise ValidationError(message="Invalid priority")
    allowed_priorities = {p.value for p in TaskPriority}
    if priority not in allowed_priorities:
        raise ValidationError(message="Invalid priority", details={'priority': priority})
    try:
        estimated_duration = int(estimated_duration)
    except Exception:  # noqa: broad-except - Data layer defensive exception handling
        raise ValidationError(message="Invalid estimated_duration")
    if estimated_duration <= 0:
        raise ValidationError(message="Invalid estimated_duration")
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
        logger.exception("Failed to create task")
        try:
            conn.rollback()
        except Exception:  # noqa: broad-except - Data layer defensive exception handling
            logger.exception("Rollback failed during create_task")
        raise DatabaseError(message="Failed to create task", details={'user_id': user_id}, cause=e)


def get_task_by_id(conn: sqlite3.Connection, task_id: str) -> Optional[Dict[str, Any]]:
    """Get a task by its ID."""
    if not task_id or not isinstance(task_id, str):
        raise ValidationError(message="Invalid task_id")
    try:
        cursor = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.exception("Failed to get task by id")
        raise DatabaseError(message="Failed to get task by id", details={'task_id': task_id}, cause=e)


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
    if not user_id or not isinstance(user_id, str):
        raise ValidationError(message="Invalid user_id")
    if status is not None and (not isinstance(status, str) or status.strip() == ""):
        raise ValidationError(message="Invalid status")
    if project is not None and not isinstance(project, str):
        raise ValidationError(message="Invalid project")
    try:
        limit = int(limit)
        offset = int(offset)
    except Exception:  # noqa: broad-except - Data layer defensive exception handling
        raise ValidationError(message="Invalid pagination")
    if limit <= 0 or limit > 5000:
        raise ValidationError(message="Invalid limit")
    if offset < 0:
        raise ValidationError(message="Invalid offset")
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
    
    try:
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.exception("Failed to get tasks for user")
        raise DatabaseError(message="Failed to get tasks for user", details={'user_id': user_id}, cause=e)


def update_task(
    conn: sqlite3.Connection,
    task_id: str,
    **updates: Any
) -> Optional[Dict[str, Any]]:
    """Update a task with the given fields."""
    if not task_id or not isinstance(task_id, str):
        raise ValidationError(message="Invalid task_id")
    if not updates:
        return get_task_by_id(conn, task_id)

    allowed_fields = {
        'title', 'description', 'project', 'priority', 'status',
        'completed', 'completed_at', 'due_date', 'estimated_duration',
        'scheduled_hour', 'scheduled_minute', 'scheduled_date', 'scheduled_duration',
        'struck_forever', 'struck_today', 'struck_date',
        'strike_report', 'strike_count', 'daily_strikes'
    }
    for key in list(updates.keys()):
        if key not in allowed_fields:
            raise ValidationError(message="Invalid update field", details={'field': key})

    updates['updated_at'] = datetime.now().isoformat()
    
    set_clause = ', '.join(f'{key} = ?' for key in updates.keys())
    values = list(updates.values()) + [task_id]
    
    try:
        conn.execute(f'UPDATE tasks SET {set_clause} WHERE id = ?', values)
        conn.commit()
        return get_task_by_id(conn, task_id)
    except Exception as e:
        logger.exception("Failed to update task %s", task_id)
        try:
            conn.rollback()
        except Exception:  # noqa: broad-except - Data layer defensive exception handling
            logger.exception("Rollback failed during update_task")
        raise DatabaseError(message="Failed to update task", details={'task_id': task_id}, cause=e)


def delete_task(conn: sqlite3.Connection, task_id: str) -> bool:
    """Delete a task by its ID."""
    if not task_id or not isinstance(task_id, str):
        raise ValidationError(message="Invalid task_id")
    try:
        cursor = conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.exception("Failed to delete task %s", task_id)
        try:
            conn.rollback()
        except Exception:  # noqa: broad-except - Data layer defensive exception handling
            logger.exception("Rollback failed during delete_task")
        raise DatabaseError(message="Failed to delete task", details={'task_id': task_id}, cause=e)


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
    if not user_id or not isinstance(user_id, str):
        raise ValidationError(message="Invalid user_id")
    if not date or not isinstance(date, str):
        raise ValidationError(message="Invalid date")
    try:
        cursor = conn.execute('''
            SELECT * FROM tasks 
            WHERE user_id = ? AND scheduled_date = ?
            ORDER BY scheduled_hour, scheduled_minute
        ''', (user_id, date))
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.exception("Failed to get scheduled tasks")
        raise DatabaseError(message="Failed to get scheduled tasks", details={'user_id': user_id, 'date': date}, cause=e)


def get_tasks_by_project(
    conn: sqlite3.Connection,
    user_id: str,
    project: str
) -> List[Dict[str, Any]]:
    """Get all tasks for a user in a specific project."""
    if not user_id or not isinstance(user_id, str):
        raise ValidationError(message="Invalid user_id")
    if not project or not isinstance(project, str):
        raise ValidationError(message="Invalid project")
    try:
        cursor = conn.execute('''
            SELECT * FROM tasks 
            WHERE user_id = ? AND project = ?
            ORDER BY created_at DESC
        ''', (user_id, project))
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        logger.exception("Failed to get tasks by project")
        raise DatabaseError(message="Failed to get tasks by project", details={'user_id': user_id, 'project': project}, cause=e)


def get_user_projects(conn: sqlite3.Connection, user_id: str) -> List[str]:
    """Get all unique projects for a user."""
    if not user_id or not isinstance(user_id, str):
        raise ValidationError(message="Invalid user_id")
    try:
        cursor = conn.execute('''
            SELECT DISTINCT project FROM tasks 
            WHERE user_id = ? AND project IS NOT NULL AND project != ''
            ORDER BY project
        ''', (user_id,))
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        logger.exception("Failed to get user projects")
        raise DatabaseError(message="Failed to get user projects", details={'user_id': user_id}, cause=e)


def count_tasks(
    conn: sqlite3.Connection,
    user_id: str,
    completed: Optional[bool] = None
) -> int:
    """Count tasks for a user."""
    if not user_id or not isinstance(user_id, str):
        raise ValidationError(message="Invalid user_id")
    query = 'SELECT COUNT(*) FROM tasks WHERE user_id = ?'
    params: List[Any] = [user_id]
    
    if completed is not None:
        query += ' AND completed = ?'
        params.append(1 if completed else 0)
    
    try:
        cursor = conn.execute(query, params)
        row = cursor.fetchone()
        return int(row[0]) if row else 0
    except Exception as e:
        logger.exception("Failed to count tasks")
        raise DatabaseError(message="Failed to count tasks", details={'user_id': user_id}, cause=e)
