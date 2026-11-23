"""Shakshuka Debian package build script.

Builds a self-contained .deb (project layout + vendored Python venv at
/opt/shakshuka) via scripts/build_linux_pkg.py. This replaces the old
`fpm -s python` approach, which dropped the app's assets and crashed with
`jinja2.exceptions.TemplateNotFound: index.html` after install.

Run on Linux only. See docs/BUILD-LINUX.md.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    return subprocess.call(
        [sys.executable, str(root / "scripts" / "build_linux_pkg.py"), "deb"],
        cwd=root,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
