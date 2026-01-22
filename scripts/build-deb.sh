#!/usr/bin/env bash
# Shakshuka Linux build wrapper
# Builds a Debian .deb package using scripts/build-deb.py.
# See docs/BUILD-LINUX.md for prerequisites (fpm, Ruby, requirements-linux).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="${SCRIPT_DIR%/scripts}"

cd "$PROJECT_ROOT"

echo "Shakshuka Linux build (Debian package)"
echo "======================================="

if ! command -v fpm >/dev/null 2>&1; then
  echo "Error: fpm is not installed. See docs/BUILD-LINUX.md for setup."
  exit 1
fi

python3 scripts/build-deb.py "$@"