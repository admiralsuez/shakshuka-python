#!/usr/bin/env bash
# Shakshuka Linux build wrapper
# Builds a RedHat/Fedora/openSUSE .rpm package using scripts/build-rpm.py.
# See docs/BUILD-LINUX.md for prerequisites (fpm, Ruby, rpm-build, requirements-linux).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR%/scripts}"

cd "$PROJECT_ROOT"

echo "Shakshuka Linux build (RPM package)"
echo "===================================="

if ! command -v fpm >/dev/null 2>&1; then
  echo "Error: fpm is not installed. See docs/BUILD-LINUX.md for setup."
  exit 1
fi

if ! command -v rpmbuild >/dev/null 2>&1; then
  echo "Error: rpmbuild is not installed. Install it first:"
  echo "  Fedora/RHEL/openSUSE: sudo dnf install rpm-build"
  echo "  Debian/Ubuntu:        sudo apt install rpm rpm-build"
  exit 1
fi

python3 scripts/build-rpm.py "$@"
