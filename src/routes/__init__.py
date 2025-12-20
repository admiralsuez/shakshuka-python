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

# Notes blueprint is optional (only in newer builds)
try:  # pragma: no cover
    from .notes_routes import notes_bp  # type: ignore
except Exception:
    notes_bp = None

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
    def _register(bp, fallback_prefix: str | None = None) -> None:
        if bp is None:
            return
        bp_prefix = getattr(bp, "url_prefix", None)
        if bp_prefix:
            app.register_blueprint(bp)
            return
        if fallback_prefix:
            app.register_blueprint(bp, url_prefix=fallback_prefix)
            return
        app.register_blueprint(bp)

    _register(auth_bp, "/api/auth")
    _register(task_bp, "/api/tasks")
    _register(notes_bp, "/api/notes")
    _register(settings_bp, "/api/settings")
    _register(monitoring_bp, "/api/monitoring")
    _register(system_bp, "/api/system")
    _register(static_bp)


__all__ = ["register_routes", "task_bp", "notes_bp", "auth_bp", "settings_bp", "monitoring_bp", "system_bp", "static_bp"]
