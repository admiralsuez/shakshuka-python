"""Routes package.

Historically this package exposed several blueprints (auth, tasks,
settings, monitoring, system, static). In the current codebase, task
routes are registered directly from :mod:`src.app` and the other
modules may not exist in all builds.

This module is therefore defensive: it *tries* to import the optional
blueprint modules, but degrades gracefully when they are missing so
that importing :mod:`src.routes` never crashes the application.
"""

from __future__ import annotations

from typing import List
from flask import Flask

# Optional blueprints; each import is guarded so that missing modules do
# not cause ImportError when the routes package is imported.

auth_bp = None
settings_bp = None
monitoring_bp = None
system_bp = None
static_bp = None

try:  # pragma: no cover - optional in some builds
    from .auth_routes import auth_bp  # type: ignore
except Exception:
    auth_bp = None

try:  # pragma: no cover
    from .task_routes import task_bp  # type: ignore
except Exception:
    task_bp = None

try:  # pragma: no cover
    from .settings_routes import settings_bp  # type: ignore
except Exception:
    settings_bp = None

try:  # pragma: no cover
    from .monitoring_routes import monitoring_bp  # type: ignore
except Exception:
    monitoring_bp = None

try:  # pragma: no cover
    from .system_routes import system_bp  # type: ignore
except Exception:
    system_bp = None

try:  # pragma: no cover
    from .static_routes import static_bp  # type: ignore
except Exception:
    static_bp = None


def register_routes(app: Flask) -> None:
    """Register any available blueprints with the Flask app.

    In the current layout, `src.app` already registers the task
    blueprint explicitly, so this function is primarily for backwards
    compatibility with older entrypoints that call
    ``src.routes.register_routes(app)``.
    """
    # Only register blueprints that were imported successfully.
    if auth_bp is not None:
        app.register_blueprint(auth_bp, url_prefix="/api/auth")
    if task_bp is not None:
        app.register_blueprint(task_bp, url_prefix="/api/tasks")
    if settings_bp is not None:
        app.register_blueprint(settings_bp, url_prefix="/api/settings")
    if monitoring_bp is not None:
        app.register_blueprint(monitoring_bp, url_prefix="/api/monitoring")
    if system_bp is not None:
        app.register_blueprint(system_bp, url_prefix="/api/system")
    if static_bp is not None:
        app.register_blueprint(static_bp)


__all__ = ["register_routes", "task_bp", "auth_bp", "settings_bp", "monitoring_bp", "system_bp", "static_bp"]
