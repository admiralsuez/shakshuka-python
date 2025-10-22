"""
Input Validators - Validation functions for user input
"""
from typing import Dict, Tuple, Any
import re


def validate_task_data(task_data: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Comprehensive validation for task data.
    
    Args:
        task_data: Dictionary containing task information
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Required fields
    required_fields = ['title']
    for field in required_fields:
        if field not in task_data or not task_data[field]:
            return False, f"Missing required field: {field}"
    
    # Title validation
    title = task_data.get('title', '').strip()
    if not title:
        return False, "Task title cannot be empty"
    if len(title) > 500:
        return False, "Task title is too long (max 500 characters)"
    
    # Description validation (if present)
    description = task_data.get('description', '')
    if description and len(description) > 5000:
        return False, "Task description is too long (max 5000 characters)"
    
    # Priority validation
    priority = task_data.get('priority', 'medium')
    valid_priorities = ['low', 'medium', 'high', 'urgent']
    if priority not in valid_priorities:
        return False, f"Invalid priority. Must be one of: {', '.join(valid_priorities)}"
    
    # Status validation
    status = task_data.get('status', 'pending')
    valid_statuses = ['pending', 'in_progress', 'completed', 'archived']
    if status not in valid_statuses:
        return False, f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
    
    # Category validation (if present)
    category = task_data.get('category', '')
    if category and len(category) > 100:
        return False, "Category name is too long (max 100 characters)"
    
    # Tags validation (if present)
    tags = task_data.get('tags', [])
    if tags and not isinstance(tags, list):
        return False, "Tags must be a list"
    if tags and len(tags) > 20:
        return False, "Too many tags (max 20)"
    for tag in tags:
        if not isinstance(tag, str):
            return False, "All tags must be strings"
        if len(tag) > 50:
            return False, "Tag is too long (max 50 characters)"
    
    # Due date validation (if present)
    due_date = task_data.get('dueDate')
    if due_date and not isinstance(due_date, str):
        return False, "Due date must be a string"
    
    # Time estimate validation (if present)
    time_estimate = task_data.get('timeEstimate')
    if time_estimate is not None:
        if not isinstance(time_estimate, (int, float)):
            return False, "Time estimate must be a number"
        if time_estimate < 0:
            return False, "Time estimate cannot be negative"
        if time_estimate > 1000:
            return False, "Time estimate is too large (max 1000 hours)"
    
    return True, ""


def validate_time_format(time_str: str) -> bool:
    """
    Validate time string format (HH:MM).
    
    Args:
        time_str: Time string to validate
        
    Returns:
        True if valid, False otherwise
    """
    try:
        hours, minutes = time_str.split(':')
        hours = int(hours)
        minutes = int(minutes)
        return 0 <= hours <= 23 and 0 <= minutes <= 59
    except (ValueError, IndexError):
        return False


def validate_email(email: str) -> bool:
    """
    Validate email format.
    
    Args:
        email: Email string to validate
        
    Returns:
        True if valid email format, False otherwise
    """
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_username(username: str) -> Tuple[bool, str]:
    """
    Validate username.
    
    Args:
        username: Username to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not username:
        return False, "Username cannot be empty"
    if len(username) < 3:
        return False, "Username must be at least 3 characters long"
    if len(username) > 50:
        return False, "Username is too long (max 50 characters)"
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return False, "Username can only contain letters, numbers, hyphens, and underscores"
    return True, ""


def validate_password(password: str) -> Tuple[bool, str]:
    """
    Validate password strength.
    
    Args:
        password: Password to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not password:
        return False, "Password cannot be empty"
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if len(password) > 128:
        return False, "Password is too long (max 128 characters)"
    
    # Check for at least one letter and one number
    has_letter = any(c.isalpha() for c in password)
    has_number = any(c.isdigit() for c in password)
    
    if not has_letter:
        return False, "Password must contain at least one letter"
    if not has_number:
        return False, "Password must contain at least one number"
    
    return True, ""

