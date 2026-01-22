"""Shakshuka macOS build script.

Uses PyInstaller to build a Shakshuka.app bundle. When running on macOS,
also creates a .dmg image using hdiutil (if available).

This is intentionally minimal; see README.md for prerequisite tools.
"""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from pathlib import Path


def load_version(root: Path) -> str:
    version_file = root / "config" / "version.json"
    if not version_file.exists():
        return "8.3"
    try:
        data = json.loads(version_file.read_text(encoding="utf-8"))
        return str(data.get("version", "8.3"))
    except Exception:  # noqa: BLE001 - defensive
        return "8.3"


def run_pyinstaller(root: Path) -> bool:
    """Run PyInstaller to build Shakshuka.app in dist/.

    We deliberately keep options simple; if you already have a .spec file,
    you can replace this with a call to `pyinstaller shakshuka.spec`.
    """

    dist_dir = root / "dist"
    dist_dir.mkdir(exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--name",
        "Shakshuka",
        "--noconfirm",
        "--clean",
        "--windowed",
        "main.py",
    ]

    print("Running PyInstaller ...")
    try:
        subprocess.run(cmd, cwd=root, check=True)
    except FileNotFoundError:
        print("Error: PyInstaller is not installed. Run `pip3 install pyinstaller`.\n")
        return False
    except subprocess.CalledProcessError as exc:  # noqa: BLE001
        print("PyInstaller failed with exit code", exc.returncode)
        return False

    app_path = dist_dir / "Shakshuka.app"
    if not app_path.exists():
        print("Expected app bundle not found:", app_path)
        return False

    print("PyInstaller build complete:", app_path)
    return True


def maybe_create_dmg(root: Path, version: str) -> None:
    if platform.system() != "Darwin":
        print("Not on macOS; skipping DMG creation.")
        return

    dist_dir = root / "dist"
    app_path = dist_dir / "Shakshuka.app"
    if not app_path.exists():
        print("Cannot create DMG; app bundle missing at", app_path)
        return

    dmg_path = dist_dir / f"Shakshuka-v{version}.dmg"
    print("Creating DMG:", dmg_path)

    cmd = [
        "hdiutil",
        "create",
        "-volname",
        "Shakshuka",
        "-srcfolder",
        str(app_path),
        "-ov",
        "-format",
        "UDZO",
        str(dmg_path),
    ]

    try:
        subprocess.run(cmd, cwd=dist_dir, check=True)
    except FileNotFoundError:
        print("Warning: hdiutil not found; skipping DMG creation.")
    except subprocess.CalledProcessError as exc:  # noqa: BLE001
        print("hdiutil failed with exit code", exc.returncode)
        return

    print("DMG created:", dmg_path)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    version = load_version(root)

    print("Shakshuka macOS build")
    print("Root:", root)
    print("Version:", version)

    if not run_pyinstaller(root):
        return 1

    maybe_create_dmg(root, version)

    print("\nmacOS build complete. Check dist/ for Shakshuka.app and any .dmg files.")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())