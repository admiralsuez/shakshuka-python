"""
Input Validators - Validation functions for user input
"""
from typing import Dict, Tuple, Any
import re
from datetime import datetime


def validate_task_data(task_data: Dict[str, Any]) -> Tuple[bool, str]:
    """Comprehensive validation for task data used by the API layer.

    This is the canonical task validator; the Flask app imports and uses this
    implementation instead of defining its own version.
    """
    if not isinstance(task_data, dict):
        return False, "Task data must be a dictionary"

    # Required fields
    required_fields = ["title"]
    for field in required_fields:
        if field not in task_data:
            return False, f"Missing required field: {field}"

    # Title validation
    title = task_data.get("title", "")
    if not isinstance(title, str) or len(title.strip()) == 0:
        return False, "Title must be a non-empty string"
    if len(title) > 200:
        return False, "Title must be less than 200 characters"

    # Description validation
    description = task_data.get("description", "")
    if description and (not isinstance(description, str) or len(description) > 1000):
        return False, "Description must be a string less than 1000 characters"

    # Project validation
    project = task_data.get("project", "")
    if project and (not isinstance(project, str) or len(project) > 100):
        return False, "Project name must be a string less than 100 characters"

    # Priority validation
    priority = task_data.get("priority", "medium")
    if priority not in ["low", "medium", "high"]:
        return False, "Priority must be 'low', 'medium', or 'high'"

    # Status validation
    status = task_data.get("status", "pending")
    if status not in ["pending", "in_progress", "completed"]:
        return False, "Status must be 'pending', 'in_progress', or 'completed'"

    # Duration validation
    duration = task_data.get("estimated_duration", 60)
    if not isinstance(duration, int) or duration < 5 or duration > 480:
        return False, "Duration must be between 5 and 480 minutes"

    # Boolean fields validation
    boolean_fields = ["completed", "struck_today"]
    for field in boolean_fields:
        if field in task_data and not isinstance(task_data[field], bool):
            return False, f"{field} must be a boolean value"

    # Numeric fields validation
    numeric_fields = ["scheduled_hour", "scheduled_duration", "strike_count"]
    for field in numeric_fields:
        if field in task_data:
            value = task_data[field]
            if value is not None and (not isinstance(value, int) or value < 0):
                return False, f"{field} must be a non-negative integer"

    # Date validation (ISO 8601 strings, allow trailing 'Z')
    date_fields = ["due_date", "completed_at", "struck_date"]
    for field in date_fields:
        if field in task_data and task_data[field] is not None:
            value = task_data[field]
            if not isinstance(value, str):
                return False, f"{field} must be a string"
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return False, f"{field} must be in valid ISO format"

    return True, "Valid"


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

