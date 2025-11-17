# Install AppIndicator for System Tray on Linux

## Problem

When running `shakshuka` on Linux, getting error:
```
Error initializing data manager: Namespace AyatanaAppIndicator3 not available
```

## Root Cause

`pystray` library tries multiple system tray backends on Linux:
1. **GTK** (Gtk) - Primary backend
2. **AyatanaAppIndicator3** - Ubuntu Unity backend
3. **AppIndicator3** - Older Ubuntu backend

If GTK isn't available, it tries AppIndicator, which also needs to be installed.

## Solution

### Option 1: Install GTK (Recommended)

```bash
sudo apt-get update
sudo apt-get install -y python3-gi gir1.2-gtk-3.0
```

### Option 2: Install AppIndicator (Alternative)

```bash
sudo apt-get update
sudo apt-get install -y gir1.2-ayatanaappindicator3-0.1
```

### Option 3: Install Both (Best Compatibility)

```bash
sudo apt-get update
sudo apt-get install -y python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1
```

## After Installation

### 1. Reinstall Package (if already installed)

```bash
sudo apt-get remove shakshuka
sudo dpkg -i dist/shakshuka_8.3_all.deb
sudo apt-get install -f
```

### 2. Test System Tray

```bash
shakshuka
```

The system tray icon should now appear in the notification area.

## Verify Installation

```bash
# Check GTK
python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk; print('✅ GTK available')"

# Check AppIndicator
python3 -c "import gi; gi.require_version('AyatanaAppIndicator3', '0.1'); from gi.repository import AyatanaAppIndicator3; print('✅ AppIndicator available')"
```

## Notes

- **System tray is optional** - App works fine without it
- **GTK is preferred** - More compatible across Linux distributions
- **AppIndicator is Ubuntu-specific** - For Unity desktop environment
- **App will work without system tray** - Just no tray icon

## What Was Fixed

- ✅ Error handling for AppIndicator errors
- ✅ App continues to work without system tray
- ✅ Better error messages for missing libraries
- ✅ Package rebuilt with fixes


