# Install GTK Libraries for System Tray on Linux

## Why GTK is Needed

`pystray` library requires GTK (GObject Introspection) on Linux for system tray functionality. Without GTK, the system tray icon won't work, but the app will still function normally.

## Install GTK Libraries

### Ubuntu/Debian

```bash
# Update package list
sudo apt-get update

# Install GTK libraries
sudo apt-get install -y python3-gi gir1.2-gtk-3.0

# Verify installation
python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk; print('GTK installed successfully')"
```

### Fedora/RHEL

```bash
sudo dnf install -y python3-gobject gtk3
```

### Arch Linux

```bash
sudo pacman -S python-gobject gtk3
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

## Verify GTK Installation

```bash
# Check if GTK is available
python3 -c "import gi; gi.require_version('Gtk', '3.0'); from gi.repository import Gtk; print('✅ GTK 3.0 is available')"
```

## Troubleshooting

### GTK not found after installation

```bash
# Reinstall GTK
sudo apt-get install --reinstall python3-gi gir1.2-gtk-3.0

# Check Python path
python3 -c "import sys; print(sys.path)"
```

### System tray still not working

1. Check if GTK is installed:
   ```bash
   python3 -c "import gi; gi.require_version('Gtk', '3.0')"
   ```

2. Check if pystray can use GTK:
   ```bash
   python3 -c "import pystray; print('pystray available')"
   ```

3. Restart the app after installing GTK

## Notes

- GTK is only needed for system tray functionality
- App works fine without GTK (just no tray icon)
- GTK installation is optional but recommended for full functionality


