"""
Path Resolution Utilities - Centralized path logic for both dev and frozen modes

This module eliminates duplicated path resolution logic throughout the codebase.
It provides functions for resolving paths in both development and PyInstaller frozen modes.
"""

import os
import sys
from typing import Optional


def get_root_dir() -> str:
    """
    Get the application root directory.
    
    Works in both development mode and PyInstaller frozen executable mode.
    
    Returns:
        Path to the root application directory
    """
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller frozen executable
        return os.path.dirname(sys.executable)
    else:
        # Running as development script
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_static_dir() -> str:
    """
    Get the static assets directory.
    
    Returns:
        Path to static assets directory (assets/static)
    """
    return os.path.join(get_root_dir(), 'assets', 'static')


def get_template_dir() -> str:
    """
    Get the templates directory.
    
    Returns:
        Path to templates directory (assets/templates)
    """
    return os.path.join(get_root_dir(), 'assets', 'templates')


def get_config_dir() -> str:
    """
    Get the configuration directory.
    
    Returns:
        Path to config directory
    """
    return os.path.join(get_root_dir(), 'config')


def get_user_data_dir() -> str:
    """
    Get user data directory that's always writable.
    
    Uses AppData on Windows and ~/.shakshuka on Unix-like systems.
    This avoids permission issues when the app is installed in Program Files.
    
    Returns:
        Path to user data directory
    """
    if os.name == 'nt':  # Windows
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        return os.path.join(appdata, 'Shakshuka')
    else:  # Unix-like systems
        return os.path.expanduser('~/.shakshuka')


def get_logs_dir() -> str:
    """
    Get the logs directory, creating it if necessary.
    
    Returns:
        Path to logs directory
    """
    logs_dir = os.path.join(get_user_data_dir(), 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir


def get_database_path() -> str:
    """
    Get the SQLite database file path.
    
    Returns:
        Path to the database file
    """
    return os.path.join(get_user_data_dir(), 'tasks.db')


def get_secret_key_path() -> str:
    """
    Get the Flask secret key file path.
    
    Returns:
        Path to the .flask_secret file
    """
    return os.path.join(get_user_data_dir(), '.flask_secret')


def get_version_path() -> str:
    """
    Get the version.json file path.
    
    Returns:
        Path to version.json
    """
    return os.path.join(get_config_dir(), 'version.json')


def get_changelog_path() -> str:
    """
    Get the changelog file path.
    
    Returns:
        Path to changelog.txt
    """
    return os.path.join(get_config_dir(), 'changelog.txt')


def ensure_user_data_dir() -> str:
    """
    Ensure user data directory exists and is writable.
    
    Returns:
        Path to user data directory
    """
    user_data_dir = get_user_data_dir()
    os.makedirs(user_data_dir, exist_ok=True)
    return user_data_dir


def ensure_logs_dir() -> str:
    """
    Ensure logs directory exists and is writable.
    
    Returns:
        Path to logs directory
    """
    logs_dir = get_logs_dir()
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir


# Convenience aliases for common usage
root_dir = get_root_dir()
static_dir = get_static_dir()
template_dir = get_template_dir()
user_data_dir = get_user_data_dir()
