"""
Application-wide constants and enums

All environment variables are centralized here with sensible defaults.
Consumers should import from this module rather than reading os.getenv directly.
"""
import os
from enum import Enum, auto
from typing import Final


# =============================================================================
# Server Configuration (from environment)
# =============================================================================
DEFAULT_HOST: Final[str] = os.getenv('SHAKSHUKA_HOST', '0.0.0.0')
DEFAULT_PORT: Final[int] = int(os.getenv('SHAKSHUKA_PORT', '8989'))
DEBUG_MODE: Final[bool] = os.getenv('SHAKSHUKA_DEBUG', 'true').lower() in {'1', 'true', 'yes'}
AUTH_ENABLED: Final[bool] = os.getenv('SHAKSHUKA_AUTH_ENABLED', 'false').lower() in {'1', 'true', 'yes'}

# =============================================================================
# Database Configuration
# =============================================================================
DB_POOL_SIZE: Final[int] = int(os.getenv('SHAKSHUKA_DB_POOL_SIZE', '5'))

# =============================================================================
# Logging Configuration
# =============================================================================
LOG_LEVEL: Final[str] = os.getenv('SHAKSHUKA_LOG_LEVEL', 'INFO')
LOG_FORMAT: Final[str] = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'


class TaskStatus(str, Enum):
    """Status values for tasks"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DEFERRED = "deferred"


class InboxStatus(str, Enum):
    """Status values for mobile inbox submissions"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class TaskPriority(str, Enum):
    """Priority levels for tasks"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class RecurrenceType(str, Enum):
    """Recurrence types for recurring tasks"""
    NONE = "none"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"

# =============================================================================
# Retry and Database Connection Configuration
# =============================================================================
MAX_RETRIES: Final[int] = int(os.getenv('SHAKSHUKA_MAX_RETRIES', '3'))
RETRY_DELAY_SECONDS: Final[float] = float(os.getenv('SHAKSHUKA_RETRY_DELAY', '0.1'))
DB_CONNECTION_TIMEOUT: Final[int] = int(os.getenv('SHAKSHUKA_DB_TIMEOUT', '30'))
DB_POOL_WAIT_TIMEOUT: Final[float] = float(os.getenv('SHAKSHUKA_DB_POOL_WAIT_TIMEOUT', '5'))

# CSRF configuration
CSRF_TOKEN_EXPIRY_SECONDS = 3600  # 1 hour

# Rate limiting
RATE_LIMIT_REQUESTS = int(os.getenv('RATE_LIMIT_REQUESTS', '100'))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv('RATE_LIMIT_WINDOW', '60'))

# Validation limits
MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 1000
MAX_PROJECT_LENGTH = 100
MIN_DURATION_MINUTES = 5
MAX_DURATION_MINUTES = 480

# DPI scale limits
MIN_DPI_SCALE = 50
MAX_DPI_SCALE = 200

# Auto-save configuration
MIN_AUTOSAVE_INTERVAL = 5
MAX_AUTOSAVE_INTERVAL = 300
DEFAULT_AUTOSAVE_INTERVAL = 30

# Request size limits
MAX_CONTENT_LENGTH_BYTES = 16 * 1024 * 1024  # 16MB
MAX_STRING_LENGTH = 10000
MAX_LIST_SIZE = 100

# Backup configuration
BACKUP_RETENTION_DAYS = 7
MAX_BACKUP_SIZE_MB = 512
MAX_BACKUP_SIZE_BYTES = MAX_BACKUP_SIZE_MB * 1024 * 1024

# Session configuration
SESSION_LIFETIME_HOURS = 24

# Health check timeouts
HEALTH_CHECK_TIMEOUT_SECONDS = 5

# GitHub configuration (from environment)
# Defaults set to the provided repository
GITHUB_REPO_OWNER = os.getenv('GITHUB_REPO_OWNER', 'admiralsuez')
GITHUB_REPO_NAME = os.getenv('GITHUB_REPO_NAME', 'shakshuka-python')

# CORS configuration
ALLOWED_ORIGINS = os.getenv('ALLOWED_ORIGINS', '*').split(',')

# Default user
DEFAULT_USER_ID = 'default_user'
