"""Build self-contained Linux packages (.deb / .rpm) for Shakshuka.

Why this exists: the previous approach (`fpm -s python setup.py`) installed the
Python source into site-packages/dist-packages WITHOUT the project's runtime
assets (assets/templates, assets/static, config/), so the packaged app crashed
on launch (TemplateNotFound: index.html, missing config/version.json).

This builder instead ships the full project layout under /opt/shakshuka/ plus
a vendored Python venv, so the packaged app is self-contained:

    /opt/shakshuka/main.py
    /opt/shakshuka/src/...
    /opt/shakshuka/assets/...
    /opt/shakshuka/config/...
    /opt/shakshuka/tools/...
    /opt/shakshuka/venv/...          (deps installed at BUILD time)
    /opt/shakshuka/shakshuka         (launcher script)
    /usr/bin/shakshuka -> /opt/shakshuka/shakshuka  (via package postinst)
    /usr/share/applications/shakshuka.desktop       (app menu entry)

Must be run on Linux (fpm + rpmbuild are Linux tools; the venv must match the
target platform). On CI this runs on ubuntu-latest for both .deb and .rpm.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Files/dirs shipped inside /opt/shakshuka/
# tools/autostart.py is the only tools module imported at runtime
# (src/app.py); docs/ is internal working notes and stays out of packages.
INCLUDE = ["main.py", "src", "assets", "config", "tools/autostart.py"]


def load_version(root: Path) -> str:
    version_file = root / "config" / "version.json"
    try:
        return str(json.loads(version_file.read_text(encoding="utf-8")).get("version", "8.3"))
    except Exception:  # noqa: BLE001 - defensive
        return "8.3"


def stage_source_tree(root: Path, staging: Path) -> Path:
    """Copy the runnable project into staging/opt/shakshuka/."""
    app_root = staging / "opt" / "shakshuka"
    app_root.mkdir(parents=True, exist_ok=True)

    for item in INCLUDE:
        src = root / item
        if not src.exists():
            print(f"  (skipping missing {item})")
            continue
        dst = app_root / item
        if src.is_dir():
            def _ignore(dir_, names):
                return [n for n in names if n == "__pycache__" or n.endswith((".pyc", ".pyo"))]
            shutil.copytree(src, dst, ignore=_ignore)
            print(f"  copied {item}/")
        else:
            shutil.copy2(src, dst)
            print(f"  copied {item}")

    return app_root


def create_venv(app_root: Path, requirements: Path) -> Path:
    """Create a Python venv inside the package and install the Linux deps."""
    venv_dir = app_root / "venv"
    print(f"\nCreating vendored venv in {venv_dir} ...")
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)

    venv_pip = venv_dir / "bin" / "pip"
    print("Installing Linux requirements into venv (this can take a minute) ...")
    subprocess.run(
        [str(venv_pip), "install", "--no-cache-dir", "-r", str(requirements)],
        check=True,
    )
    return venv_dir


def write_launcher(app_root: Path) -> None:
    launcher = app_root / "shakshuka"
    launcher.write_text(
        "#!/usr/bin/env sh\n"
        "cd /opt/shakshuka || exit 1\n"
        'exec /opt/shakshuka/venv/bin/python /opt/shakshuka/main.py "$@"\n',
        encoding="utf-8",
    )
    launcher.chmod(0o755)
    print("  wrote launcher script")


def write_desktop_entry(staging: Path) -> None:
    desktop_dir = staging / "usr" / "share" / "applications"
    desktop_dir.mkdir(parents=True, exist_ok=True)
    (desktop_dir / "shakshuka.desktop").write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=Shakshuka\n"
        "Comment=Shakshuka Task Manager\n"
        "Exec=/opt/shakshuka/shakshuka\n"
        "Icon=/opt/shakshuka/assets/static/images/icon.png\n"
        "Terminal=false\n"
        "Categories=Utility;Office;\n"
        "StartupNotify=true\n",
        encoding="utf-8",
    )
    print("  wrote .desktop entry")


def write_scripts(staging: Path) -> tuple[Path, Path]:
    """Write postinst (symlink /usr/bin/shakshuka) and prerm (remove it)."""
    scripts_dir = staging.parent / "pkgscripts"
    scripts_dir.mkdir(exist_ok=True)
    postinst = scripts_dir / "postinst.sh"
    postinst.write_text(
        "#!/bin/sh\n"
        "set -e\n"
        "ln -sf /opt/shakshuka/shakshuka /usr/bin/shakshuka\n"
        "command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database >/dev/null 2>&1 || true\n"
        "exit 0\n",
        encoding="utf-8",
    )
    prerm = scripts_dir / "prerm.sh"
    prerm.write_text(
        "#!/bin/sh\n"
        "set -e\n"
        "rm -f /usr/bin/shakshuka\n"
        "exit 0\n",
        encoding="utf-8",
    )
    postinst.chmod(0o755)
    prerm.chmod(0o755)
    return postinst, prerm


def run_fpm(format_: str, staging: Path, version: str, out_dir: Path) -> bool:
    out_dir.mkdir(exist_ok=True)
    package_name = f"shakshuka-{version}-1.x86_64.rpm" if format_ == "rpm" else f"shakshuka_{version}_amd64.deb"
    out_file = out_dir / package_name

    cmd = [
        "fpm",
        "-s", "dir",
        "-t", format_,
        "-C", str(staging),
        "--name", "shakshuka",
        "--version", version,
        "--license", "MIT",
        "--vendor", "vibinandvanshika.in",
        "--url", "https://github.com/admiralsuez/shakshuka-python",
        "--description", "Shakshuka Task Manager (self-contained build with bundled Python venv)",
        "--architecture", "amd64" if format_ == "deb" else "x86_64",
        "--after-install", str(staging.parent / "pkgscripts" / "postinst.sh"),
        "--before-remove", str(staging.parent / "pkgscripts" / "prerm.sh"),
        "--package", str(out_file),
        "--force",
        # Include everything staged below
        "opt",
        "usr/share/applications/shakshuka.desktop",
    ]

    print(f"\nBuilding .{format_} with fpm ...")
    try:
        subprocess.run(cmd, check=True)
        print(f"Created: {out_file}")
        return True
    except FileNotFoundError:
        print("Error: fpm not found on PATH. Install with `sudo gem install fpm`.")
        return False
    except subprocess.CalledProcessError as exc:
        print(f"fpm failed with exit code {exc.returncode}")
        return False


def main() -> int:
    if os.name != "posix":
        print("This Linux package builder must run on Linux (fpm + vendored venv).")
        print("Use the GitHub Actions 'release.yml' workflow to build on ubuntu-latest.")
        return 1

    format_arg = "both"
    if len(sys.argv) > 1 and sys.argv[1] in ("deb", "rpm", "both"):
        format_arg = sys.argv[1]

    root = Path(__file__).resolve().parents[1]
    version = load_version(root)
    requirements = root / "config" / "requirements-linux.txt"
    if not requirements.exists():
        print(f"Missing {requirements}")
        return 1

    print("Shakshuka Linux package build (self-contained /opt layout)")
    print("Root:", root)
    print("Version:", version)
    print("Formats:", format_arg)

    work = Path(tempfile.mkdtemp(prefix="shakshuka-pkg-"))
    staging = work / "staging"
    try:
        staging.mkdir(parents=True, exist_ok=True)
        app_root = stage_source_tree(root, staging)
        create_venv(app_root, requirements)
        write_launcher(app_root)
        write_desktop_entry(staging)
        write_scripts(staging)

        out_dir = root / "dist"
        ok = True
        if format_arg in ("deb", "both"):
            ok = run_fpm("deb", staging, version, out_dir) and ok
        if format_arg in ("rpm", "both"):
            ok = run_fpm("rpm", staging, version, out_dir) and ok

        if ok:
            print(f"\nDone. Packages are in {out_dir}")
            return 0
        return 1
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
