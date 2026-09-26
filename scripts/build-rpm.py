"""Shakshuka RPM package build script.

Creates a .rpm using fpm and the existing setup.py.
See docs/BUILD-LINUX.md and README.md for prerequisites.

RPM targets additionally require `rpmbuild` (Fedora/RHEL/openSUSE:
`sudo dnf install rpm-build`); run this script on a Linux machine,
it cannot produce an RPM on Windows.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def load_version(root: Path) -> str:
    """Load version string from config/version.json, fallback to 8.3."""
    version_file = root / "config" / "version.json"
    if not version_file.exists():
        return "8.3"
    try:
        data = json.loads(version_file.read_text(encoding="utf-8"))
        return str(data.get("version", "8.3"))
    except Exception:  # noqa: BLE001 - defensive
        return "8.3"


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    setup_py = root / "setup.py"
    if not setup_py.exists():
        print("setup.py not found at", setup_py)
        return 1

    version = load_version(root)

    print("Shakshuka RPM package build")
    print("Root:", root)
    print("Version:", version)
    print("Using fpm to build .rpm ...")

    # Note: we intentionally do not install dependencies here; user/CI should
    # have run `pip3 install -r config/requirements-linux.txt` already.

    cmd = [
        "fpm",
        "-s",
        "python",
        "-t",
        "rpm",
        "--python-bin",
        "python3",
        "--python-pip",
        "pip3",
        "--python-package-name-prefix",
        "python3",
        "--no-python-dependencies",
        "--name",
        "shakshuka",
        "--version",
        version,
        "--description",
        "Shakshuka application",
        str(setup_py),
    ]

    try:
        subprocess.run(cmd, cwd=root, check=True)
    except FileNotFoundError:
        print("Error: fpm not found on PATH. See docs/BUILD-LINUX.md.")
        print("Hint: RPM output also needs rpm-build (e.g. `sudo dnf install rpm-build`).")
        return 1
    except subprocess.CalledProcessError as exc:  # noqa: BLE001
        print("fpm failed with exit code", exc.returncode)
        if exc.returncode:
            print(
                "Hint: -t rpm requires rpmbuild. Install it with "
                "`sudo dnf install rpm-build` (Fedora/RHEL) or "
                "`sudo apt install rpm rpm-build` (Debian/Ubuntu)."
            )
        return exc.returncode or 1

    print("\nRPM package build complete.")
    print("Check the dist/ directory for the resulting .rpm file.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
