#!/usr/bin/env bash
# Shakshuka macOS build wrapper
# Builds a .app bundle (and .dmg when on macOS) using scripts/build-mac.py.
# See README.md for prerequisites (PyInstaller, Python deps).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR%/scripts}"

cd "$PROJECT_ROOT"

echo "Shakshuka macOS build (.app / .dmg)"
echo "===================================="

python3 scripts/build-mac.py "$@"