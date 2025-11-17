# Fix: No module named 'winreg' Error on Linux

## Problem

When running `shakshuka` on Linux, getting error:
```
Error initializing data manager: No module named 'winreg'
```

## Root Cause

`tools/autostart.py` was importing `winreg` at the top level, which is a Windows-only module. When the package is installed on Linux, importing `WindowsAutostart` tries to import `winreg`, which doesn't exist on Linux.

## Solution Applied

Made `tools/autostart.py` platform-aware:
- Conditionally import `winreg` only on Windows
- Added platform checks in all methods
- Methods return `False` or `None` on Linux (autostart not available)

## Steps to Fix

### 1. Uninstall Old Package

```bash
sudo apt-get remove shakshuka
```

### 2. Reinstall Updated Package

```bash
cd /mnt/d/shakshuka-python
sudo dpkg -i dist/shakshuka_8.3_all.deb
sudo apt-get install -f
```

### 3. Install Dependencies (if not already installed)

```bash
pip3 install -r config/requirements-linux.txt
```

### 4. Test Command

```bash
shakshuka
```

## What Was Fixed

- ✅ `tools/autostart.py` - Platform-aware import of `winreg`
- ✅ All methods check platform before using `winreg`
- ✅ Package rebuilt with fixes

## Notes

- Autostart functionality is Windows-only
- On Linux, autostart methods will return `False` (not available)
- App will work on Linux, just without autostart feature


