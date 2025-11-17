#!/bin/bash
# Post-installation script for shakshuka package
# This script installs the Python package with entry points

set -e

# Find the package directory
PACKAGE_DIR="/usr/share/shakshuka"
SETUP_PY="$PACKAGE_DIR/setup.py"

# If setup.py exists in package directory, install it
if [ -f "$SETUP_PY" ]; then
    echo "Installing shakshuka Python package..."
    python3 -m pip install "$PACKAGE_DIR" --no-deps --force-reinstall --quiet
    echo "✅ shakshuka package installed successfully"
else
    # Try to find setup.py in common locations
    if [ -f "/opt/shakshuka/setup.py" ]; then
        echo "Installing shakshuka Python package from /opt/shakshuka..."
        python3 -m pip install /opt/shakshuka --no-deps --force-reinstall --quiet
        echo "✅ shakshuka package installed successfully"
    else
        echo "⚠️  Warning: setup.py not found. Entry points may not be created."
        echo "You can manually install with: python3 -m pip install /path/to/setup.py --no-deps"
    fi
fi

# Update PATH if needed
if [ -d "$HOME/.local/bin" ] && ! echo "$PATH" | grep -q "$HOME/.local/bin"; then
    echo "⚠️  Note: Add ~/.local/bin to your PATH if shakshuka command is not found"
fi

exit 0


