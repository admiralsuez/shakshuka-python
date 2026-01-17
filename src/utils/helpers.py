"""
Helper Utilities - Common helper functions

This module contains common utility functions used throughout the application.
"""

import json
import logging
from typing import Tuple
from src.utils.paths import get_version_path

logger = logging.getLogger(__name__)


def get_app_version() -> str:
    """
    Load application version from config file.
    
    Works in both development and frozen modes.
    
    Returns:
        Version string in format "MAJOR.MINOR.BUILD" (e.g., "6.2.1")
    """
    try:
        version_path = get_version_path()
        with open(version_path, 'r') as f:
            version_data = json.load(f)
        return f"{version_data['version']}.{version_data['build']}"
    except (OSError, json.JSONDecodeError, KeyError):
        logger.exception("Failed to read version.json, falling back to 1.0.0")
        return '1.0.0'


def is_newer_version(new_version: str, current_version: str) -> bool:
    """
    Compare two version strings to determine if new_version is newer.
    
    Performs semantic version comparison by breaking down version strings
    into numeric components and comparing them lexicographically.
    
    Args:
        new_version: Version string to check (e.g., "6.2.1")
        current_version: Current version string (e.g., "6.1.0")
    
    Returns:
        True if new_version is newer than current_version, False otherwise
    """
    try:
        new_parts = [int(x) for x in str(new_version).split('.')]
        cur_parts = [int(x) for x in str(current_version).split('.')]
        
        # Pad shorter version with zeros for comparison
        max_len = max(len(new_parts), len(cur_parts))
        new_parts += [0] * (max_len - len(new_parts))
        cur_parts += [0] * (max_len - len(cur_parts))
        
        return new_parts > cur_parts
    except (TypeError, ValueError):
        logger.exception("Error comparing versions: %r vs %r", new_version, current_version)
        return False


def parse_version_string(version_str: str) -> Tuple[int, int, int]:
    """
    Parse a version string into major, minor, patch components.
    
    Args:
        version_str: Version string (e.g., "6.2.1" or "6.2")
    
    Returns:
        Tuple of (major, minor, patch) integers
    """
    try:
        parts = [int(x) for x in str(version_str).split('.')]
        # Pad with zeros if needed
        while len(parts) < 3:
            parts.append(0)
        return tuple(parts[:3])
    except (TypeError, ValueError):
        logger.exception("Could not parse version string: %r", version_str)
        return (1, 0, 0)


def format_version(major: int, minor: int, patch: int = 0) -> str:
    """
    Format version components into a version string.
    
    Args:
        major: Major version number
        minor: Minor version number
        patch: Patch version number (default 0)
    
    Returns:
        Version string (e.g., "6.2.1")
    """
    return f"{major}.{minor}.{patch}"


def clamp(value, min_value, max_value):
    """
    Clamp a value between min and max values.
    
    Args:
        value: Value to clamp
        min_value: Minimum value
        max_value: Maximum value
    
    Returns:
        Clamped value
    """
    return max(min_value, min(max_value, value))


def chunks(lst, n):
    """
    Split a list into chunks of size n.
    
    Args:
        lst: List to split
        n: Chunk size
    
    Yields:
        Chunks of the list
    """
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def safe_get_nested(d: dict, keys: list, default=None):
    """
    Safely get a nested value from a dictionary.
    
    Args:
        d: Dictionary to search
        keys: List of keys to traverse (e.g., ['key1', 'key2', 'key3'])
        default: Default value if key path doesn't exist
    
    Returns:
        Value at the key path, or default if not found
    """
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key)
        else:
            return default
    return d if d is not None else default


def merge_dicts(base: dict, override: dict) -> dict:
    """
    Deep merge override dict into base dict.
    
    Args:
        base: Base dictionary
        override: Dictionary with values to override
    
    Returns:
        Merged dictionary
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def dict_from_keys(keys: list, value=None) -> dict:
    """
    Create a dictionary from a list of keys with a default value.
    
    Args:
        keys: List of keys
        value: Default value for all keys
    
    Returns:
        Dictionary with keys mapped to value
    """
    return {key: value for key in keys}


def is_valid_uuid(value: str) -> bool:
    """
    Check if a string is a valid UUID.
    
    Args:
        value: String to check
    
    Returns:
        True if valid UUID format, False otherwise
    """
    import uuid
    try:
        uuid.UUID(str(value))
        return True
    except ValueError:
        return False


def sanitize_dict_for_json(d: dict) -> dict:
    """
    Recursively sanitize a dictionary for JSON serialization.
    
    Converts non-JSON-serializable types to strings.
    
    Args:
        d: Dictionary to sanitize
    
    Returns:
        Sanitized dictionary
    """
    from datetime import datetime
    
    result = {}
    for key, value in d.items():
        if isinstance(value, dict):
            result[key] = sanitize_dict_for_json(value)
        elif isinstance(value, (list, tuple)):
            result[key] = [
                sanitize_dict_for_json(item) if isinstance(item, dict) else
                str(item) if isinstance(item, datetime) else
                item
                for item in value
            ]
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, (str, int, float, bool, type(None))):
            result[key] = value
        else:
            # Convert other types to string
            result[key] = str(value)
    return result
