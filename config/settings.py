"""
Application settings and configuration constants.
Centralized location for all configurable values.
"""

from typing import Final

# Server Configuration
SERVER_HOST: Final[str] = "127.0.0.1"
SERVER_PORT: Final[int] = 8989
SERVER_DEBUG: Final[bool] = False

# Timeouts (in seconds)
REQUEST_TIMEOUT: Final[int] = 30
CONNECTION_TIMEOUT: Final[int] = 10
MOBILE_PAIRING_TIMEOUT: Final[int] = 300  # 5 minutes
MOBILE_POLLING_INTERVAL: Final[float] = 2.5
DATABASE_TIMEOUT: Final[int] = 30
HEALTH_CHECK_TIMEOUT: Final[int] = 5

# Database Configuration
DATABASE_NAME: Final[str] = "shakshuka.db"
DATABASE_BACKUP_COUNT: Final[int] = 5

# Task Configuration
DEFAULT_TASK_DURATION: Final[int] = 30  # minutes
MIN_TASK_DURATION: Final[int] = 5
MAX_TASK_DURATION: Final[int] = 480  # 8 hours

# Auto-save Configuration
AUTOSAVE_INTERVAL: Final[int] = 60  # seconds
AUTOSAVE_ENABLED: Final[bool] = True

# Session Configuration
SESSION_LIFETIME: Final[int] = 86400  # 24 hours in seconds
MAX_SESSIONS_PER_USER: Final[int] = 5

# Mobile Sync Configuration
MOBILE_INBOX_MAX_ENTRIES: Final[int] = 50
MOBILE_HISTORY_MAX_ENTRIES: Final[int] = 100

# Analytics Configuration
ANALYTICS_RETENTION_DAYS: Final[int] = 365
PRODUCTIVITY_STREAK_THRESHOLD: Final[int] = 1  # minimum tasks for streak

# UI Configuration
TASKS_PER_PAGE: Final[int] = 50
MAX_TITLE_LENGTH: Final[int] = 200
MAX_DESCRIPTION_LENGTH: Final[int] = 2000

# File paths (relative to app root)
DATA_DIR: Final[str] = "data"
BACKUP_DIR: Final[str] = "data/backups"
LOG_DIR: Final[str] = "logs"
