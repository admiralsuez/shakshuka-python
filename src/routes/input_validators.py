"""
Input Validators - Validation helpers for common inputs
"""

from typing import Tuple, Optional
from datetime import datetime


def validate_schedule_input(hour: int, minute: int = 0, duration: int = 30) -> Tuple[bool, str]:
    """Validate schedule input (hour, minute, duration)
    
    Args:
        hour: Hour (0-23)
        minute: Minute (0-59), default 0
        duration: Duration in minutes (1-480), default 30
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(hour, int):
        return False, "Hour must be an integer"
    if hour < 0 or hour > 23:
        return False, "Hour must be 0-23"
    
    if not isinstance(minute, int):
        return False, "Minute must be an integer"
    if minute < 0 or minute > 59:
        return False, "Minute must be 0-59"
    
    if not isinstance(duration, int):
        return False, "Duration must be an integer"
    if duration < 1 or duration > 480:
        return False, "Duration must be 1-480 minutes"
    
    return True, ""


def validate_task_title(title: str) -> Tuple[bool, str]:
    """Validate task title
    
    Args:
        title: Task title
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(title, str):
        return False, "Title must be a string"
    
    if len(title.strip()) == 0:
        return False, "Title cannot be empty"
    
    if len(title) > 500:
        return False, "Title too long (max 500 characters)"
    
    return True, ""


def validate_priority(priority: str) -> Tuple[bool, str]:
    """Validate task priority
    
    Args:
        priority: Priority level
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    valid_priorities = ['low', 'medium', 'high', 'critical']
    
    if not isinstance(priority, str):
        return False, "Priority must be a string"
    
    if priority.lower() not in valid_priorities:
        return False, f"Priority must be one of: {', '.join(valid_priorities)}"
    
    return True, ""


def validate_date_yyyy_mm_dd(date_str: str) -> Tuple[bool, str]:
    """Validate date in YYYY-MM-DD format
    
    Args:
        date_str: Date string
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(date_str, str):
        return False, "Date must be a string"
    
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return True, ""
    except ValueError:
        return False, "Date must be in YYYY-MM-DD format"


def validate_description(description: str, max_length: int = 2000) -> Tuple[bool, str]:
    """Validate task description
    
    Args:
        description: Description text
        max_length: Maximum length (default 2000)
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(description, str):
        return False, "Description must be a string"
    
    if len(description) > max_length:
        return False, f"Description too long (max {max_length} characters)"
    
    return True, ""


def validate_project_name(project: str) -> Tuple[bool, str]:
    """Validate project name
    
    Args:
        project: Project name
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(project, str):
        return False, "Project must be a string"
    
    if len(project) > 100:
        return False, "Project name too long (max 100 characters)"
    
    return True, ""


def validate_owner_name(owner: str) -> Tuple[bool, str]:
    """Validate owner name
    
    Args:
        owner: Owner name
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(owner, str):
        return False, "Owner must be a string"
    
    if len(owner) > 100:
        return False, "Owner name too long (max 100 characters)"
    
    return True, ""


def validate_strike_report(report: str, max_length: int = 2000) -> Tuple[bool, str]:
    """Validate strike report
    
    Args:
        report: Report text
        max_length: Maximum length (default 2000)
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(report, str):
        return False, "Report must be a string"
    
    if len(report) > max_length:
        return False, f"Report too long (max {max_length} characters)"
    
    return True, ""


def validate_bulk_operation_count(count: int, max_count: int = 100) -> Tuple[bool, str]:
    """Validate count for bulk operations
    
    Args:
        count: Item count
        max_count: Maximum allowed count (default 100)
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(count, int):
        return False, "Count must be an integer"
    
    if count <= 0:
        return False, "Count must be greater than 0"
    
    if count > max_count:
        return False, f"Too many items (max {max_count})"
    
    return True, ""
