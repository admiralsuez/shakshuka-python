from __future__ import annotations

from typing import Any, Optional


def set_extension(app: Any, key: str, value: Any) -> None:
    if not hasattr(app, 'extensions') or app.extensions is None:
        return
    app.extensions[key] = value


def get_extension(app: Any, key: str, default: Optional[Any] = None) -> Any:
    if not hasattr(app, 'extensions') or app.extensions is None:
        return default
    return app.extensions.get(key, default)
