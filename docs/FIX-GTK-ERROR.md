# Fix: Namespace Gtk not available Error on Linux

## Problem

When running `shakshuka` on Linux, getting error:
```
Error initializing data manager: Namespace Gtk not available
```

## Root Cause

`pystray` library requires GTK (GObject Introspection) on Linux for system tray functionality. When `pystray` is imported, it tries to initialize GTK, which isn't installed by default.

## Solution Applied

Made `pystray` import lazy (only when needed):
- Removed top-level `pystray` import
- Added `_check_system_tray_available()` function for lazy checking
- System tray initialization now catches GTK errors gracefully
- App continues to work even if system tray is unavailable

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

### 3. Test Command

```bash
shakshuka
```

## Optional: Install GTK for System Tray (if needed)

If you want system tray functionality on Linux:

```bash
sudo apt-get install python3-gi gir1.2-gtk-3.0
```

## What Was Fixed

- ✅ `src/app.py` - Lazy pystray import
- ✅ GTK errors now caught gracefully
- ✅ App works without system tray on Linux
- ✅ Package rebuilt with fixes

## Notes

- System tray is optional - app works without it
- On Linux, system tray requires GTK libraries
- App will work fine without system tray (just no tray icon)


