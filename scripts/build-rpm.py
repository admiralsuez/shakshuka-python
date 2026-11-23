"""Shakshuka RPM package build script.

Builds a self-contained .rpm (project layout + vendored Python venv at
/opt/shakshuka) via scripts/build_linux_pkg.py. The RPM target additionally
requires rpmbuild (`rpm-build` on Fedora/RHEL, `rpm rpm-build` on Debian/Ubuntu).

Run on Linux only. See docs/BUILD-LINUX.md.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    return subprocess.call(
        [sys.executable, str(root / "scripts" / "build_linux_pkg.py"), "rpm"],
        cwd=root,
    )


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
