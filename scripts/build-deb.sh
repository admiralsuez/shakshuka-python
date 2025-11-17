#!/bin/bash
# Build script for creating Debian package (.deb) using fpm
# Usage: ./scripts/build-deb.sh

set -e  # Exit on error

echo "Building Debian package for Shakshuka..."
echo "=========================================="

# Get version from version.json
VERSION_FILE="config/version.json"
if [ -f "$VERSION_FILE" ]; then
    VERSION=$(python3 -c "import json; print(json.load(open('$VERSION_FILE'))['version'])")
else
    VERSION="8.3"
fi

echo "Version: $VERSION"
echo ""

# Check if fpm is installed
if ! command -v fpm &> /dev/null; then
    echo "Error: fpm is not installed!"
    echo ""
    echo "Install fpm with:"
    echo "  sudo apt-get install ruby-dev build-essential"
    echo "  sudo gem install fpm"
    echo ""
    exit 1
fi

# Check if we're in the project root
if [ ! -f "setup.py" ]; then
    echo "Error: setup.py not found. Please run this script from the project root."
    exit 1
fi

# Create dist directory if it doesn't exist
mkdir -p dist

# Build the .deb package using fpm
echo "Creating .deb package..."
fpm -s python -t deb \
    --python-bin python3 \
    --python-pip pip3 \
    --python-package-name-prefix python3 \
    --no-python-dependencies \
    --name shakshuka \
    --version "$VERSION" \
    --description "Shakshuka application" \
    --depends python3 \
    --depends python3-pip \
    setup.py

# Check if package was created
DEB_FILE="python3-shakshuka_${VERSION}_all.deb"
if [ -f "$DEB_FILE" ]; then
    echo ""
    echo "✅ Package created successfully!"
    echo "File: $DEB_FILE"
    
    # Move to dist directory
    mv "$DEB_FILE" "dist/"
    echo "Moved to: dist/$DEB_FILE"
    
    # Show package info
    echo ""
    echo "Package information:"
    dpkg-deb -I "dist/$DEB_FILE" 2>/dev/null || echo "Install dpkg to view package info"
    
    echo ""
    echo "To install the package:"
    echo "  sudo dpkg -i dist/$DEB_FILE"
    echo "  sudo apt-get install -f  # Fix dependencies if needed"
    
else
    echo ""
    echo "❌ Error: Package file not found!"
    echo "Check the output above for errors."
    exit 1
fi

