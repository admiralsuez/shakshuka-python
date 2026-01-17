"""Core application configuration.

This module provides a dataclass interface to configuration values.
Actual values are imported from src.constants to avoid duplication.
"""

from dataclasses import dataclass, field

# Import centralized constants
from src.constants import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DEBUG_MODE,
    AUTH_ENABLED,
    SESSION_LIFETIME_HOURS,
    DB_CONNECTION_TIMEOUT,
    DB_POOL_SIZE,
    LOG_LEVEL,
    LOG_FORMAT,
)


@dataclass
class AppConfig:
    """Application configuration values.

    Values are imported from src.constants which reads environment variables.
    This class provides a convenient interface for accessing configuration.
    """

    # Network
    DEFAULT_HOST: str = field(default_factory=lambda: DEFAULT_HOST)
    DEFAULT_PORT: int = field(default_factory=lambda: DEFAULT_PORT)

    # Flask debug flag
    DEBUG: bool = field(default_factory=lambda: DEBUG_MODE)

    # Feature flags
    AUTH_ENABLED: bool = field(default_factory=lambda: AUTH_ENABLED)

    # Session
    SESSION_LIFETIME_HOURS: int = field(default_factory=lambda: SESSION_LIFETIME_HOURS)

    # Database
    DB_TIMEOUT: int = field(default_factory=lambda: DB_CONNECTION_TIMEOUT)
    DB_POOL_SIZE: int = field(default_factory=lambda: DB_POOL_SIZE)

    # Logging
    LOG_LEVEL: str = field(default_factory=lambda: LOG_LEVEL)
    LOG_FORMAT: str = field(default_factory=lambda: LOG_FORMAT)


# Singleton config instance used throughout the app
config = AppConfig()
