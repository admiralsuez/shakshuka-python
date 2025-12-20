"""Core application configuration.

This module centralizes runtime configuration values used across the
application (host/port, debug flags, etc.). It is intentionally kept
simple and can be extended in the future if more settings are needed.
"""

from dataclasses import dataclass
import os


@dataclass
class AppConfig:
    """Application configuration values.

    Values are loaded from environment variables when available, with
    sensible defaults for local/dev usage.
    """

    # Network
    DEFAULT_HOST: str = os.getenv("SHAKSHUKA_HOST", "127.0.0.1")
    DEFAULT_PORT: int = int(os.getenv("SHAKSHUKA_PORT", "8989"))

    # Flask debug flag (app still explicitly sets debug=True in dev)
    DEBUG: bool = os.getenv("SHAKSHUKA_DEBUG", "true").lower() in {"1", "true", "yes"}

    # Feature flags used by templates / frontend
    # In the current build authentication via username/password is disabled;
    # PIN auth is managed separately, so expose this as False unless
    # explicitly overridden by an environment variable.
    AUTH_ENABLED: bool = os.getenv("SHAKSHUKA_AUTH_ENABLED", "false").lower() in {"1", "true", "yes"}

    # Session
    SESSION_LIFETIME_HOURS: int = int(os.getenv("SHAKSHUKA_SESSION_LIFETIME_HOURS", "24"))


# Singleton config instance used throughout the app
config = AppConfig()
