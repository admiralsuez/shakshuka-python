# Fix: shakshuka command not found after .deb install

## Problem

After installing the .deb package, the `shakshuka` command is not found:
```
-bash: /usr/local/bin/shakshuka: No such file or directory
```

## Root Cause

The `fpm` tool with `--no-python-dependencies` doesn't properly install the Python package with entry points. The package only contains documentation files, not the actual Python package or entry points.

## Solution

### Option 1: Manual Installation (Quick Fix)

After installing the .deb package, manually install the Python package:

```bash
# Navigate to the source directory
cd /mnt/d/shakshuka-python

# Install the package with pip (this creates the entry point)
sudo python3 -m pip install . --no-deps --force-reinstall

# Verify the command exists
which shakshuka
shakshuka --help
```

### Option 2: Use Post-Install Script (Automatic)

The package now includes a post-install script that should automatically install the package. If it doesn't work, use Option 1.

### Option 3: Run Directly (No Command Needed)

You can run the app directly without the `shakshuka` command:

```bash
cd /mnt/d/shakshuka-python
python3 main.py
```

## Verify Installation

```bash
# Check if command exists
which shakshuka

# Check entry points
python3 -m pip show shakshuka | grep -A 5 "Entry-points"

# Test the command
shakshuka
```

## Notes

- The `shakshuka` command is created by setuptools entry points
- It's typically installed in `/usr/local/bin/` or `~/.local/bin/`
- Make sure `/usr/local/bin` is in your PATH: `echo $PATH`
- If using `~/.local/bin`, add it to PATH: `export PATH="$HOME/.local/bin:$PATH"`


