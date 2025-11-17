# 🍳 Shakshuka - Build Guide

Complete guide for building Shakshuka for Windows, Linux, and macOS.

---

## 📋 Quick Start

### Windows
```bash
pip install -r config/requirements.txt
python scripts/build.py
```

### Linux
```bash
sudo apt-get install ruby-dev build-essential
sudo gem install fpm
pip3 install -r config/requirements.txt
python3 scripts/build-deb.py
```

### macOS
```bash
pip3 install pyinstaller
pip3 install -r config/requirements.txt
python3 scripts/build-mac.py
```

---

## 🪟 Windows Build

### Prerequisites
- Python 3.8+
- PyInstaller: `pip install pyinstaller`
- Inno Setup 6: Download from [jrsoftware.org](https://jrsoftware.org/isinfo.php)
- Install to: `C:\Program Files (x86)\Inno Setup 6\`

### Build Steps

1. **Install dependencies:**
   ```bash
   pip install -r config/requirements.txt
   ```

2. **Run build script:**
   ```bash
   python scripts/build.py
   ```

### Output Files
- `Shakshuka.exe` - Standalone executable (project root)
- `Shakshuka-Setup-vX.X.exe` - Windows installer (project root)
- `build_reports/BUILD_REPORT_vX.X.md` - Build report

### What It Does
- ✅ Auto-increments build number
- ✅ Builds standalone EXE with PyInstaller
- ✅ Creates Windows installer with Inno Setup
- ✅ Generates build report

---

## 🐧 Linux Build (.deb Package)

### Prerequisites
- Python 3.8+
- fpm (Fancy Package Manager)
- Ruby and build tools

### Setup

1. **Install fpm:**
   ```bash
   sudo apt-get update
   sudo apt-get install ruby-dev build-essential
   sudo gem install fpm
   ```

2. **Verify installation:**
   ```bash
   fpm --version
   ```

### Build Steps

1. **Install dependencies:**
   ```bash
   pip3 install -r config/requirements.txt
   ```

2. **Run build script:**
   ```bash
   python3 scripts/build-deb.py
   ```

### Output File
- `dist/shakshuka_X.X_all.deb` - Debian package

### Install Package
```bash
sudo dpkg -i dist/shakshuka_X.X_all.deb
sudo apt-get install -f  # Fix dependencies if needed
```

---

## 🍎 macOS Build (.app + .dmg)

### Prerequisites
- macOS (required for DMG creation)
- Python 3.8+
- PyInstaller: `pip3 install pyinstaller`

### Build Steps

1. **Install dependencies:**
   ```bash
   pip3 install pyinstaller
   pip3 install -r config/requirements.txt
   ```

2. **Run build script:**
   ```bash
   python3 scripts/build-mac.py
   ```

### Output Files
- `dist/Shakshuka.app` - macOS application bundle
- `dist/Shakshuka-vX.X.dmg` - Disk image for distribution

### What It Does
- ✅ Creates `.app` bundle using PyInstaller
- ✅ Creates `.dmg` file with drag-and-drop installation
- ✅ Includes Applications folder link in DMG

### User Installation
1. Double-click `Shakshuka-vX.X.dmg` to mount it
2. Drag `Shakshuka.app` to the Applications folder
3. Eject the disk image
4. Launch from Applications

### Note
- **DMG creation requires macOS** - The script will create the `.app` bundle on any platform, but `.dmg` can only be created on macOS
- If building on Windows/Linux, transfer the `.app` bundle to a Mac to create the DMG

---

## 🔧 Prerequisites Summary

### All Platforms
```bash
pip install -r config/requirements.txt
```

### Platform-Specific

| Platform | Required Tools |
|----------|---------------|
| **Windows** | PyInstaller, Inno Setup 6 |
| **Linux** | PyInstaller, fpm, Ruby, build-essential |
| **macOS** | PyInstaller (DMG creation requires macOS) |

---

## 📝 Version Management

### Version File
- Location: `config/version.json`
- Format:
  ```json
  {
    "version": "8.3",
    "build": "1",
    "release_date": "2025-10-20T12:00:00Z",
    "update_channel": "stable"
  }
  ```

### Auto-Increment
- **Windows**: Automatically increments build number
- **Linux/macOS**: Uses version from `config/version.json`

### Manual Update
1. Edit `config/version.json`
2. Change `version` field (e.g., "8.3" → "8.4")
3. Reset `build` to "1" for new version
4. Run build script

---
## 📦 Build Artifacts

### Windows
- `Shakshuka.exe` - Standalone executable
- `Shakshuka-Setup-vX.X.exe` - Installer package
- `build_reports/BUILD_REPORT_vX.X.md` - Build report

### Linux
- `dist/shakshuka_X.X_all.deb` - Debian package

### macOS
- `dist/Shakshuka.app` - Application bundle
- `dist/Shakshuka-vX.X.dmg` - Disk image

---

## ✅ Verification Checklist

### Windows
- [ ] `Shakshuka.exe` exists and runs
- [ ] Installer package created
- [ ] Version number correct
- [ ] All features work

### Linux
- [ ] `.deb` package created in `dist/`
- [ ] Package installs without errors
- [ ] Application runs correctly
- [ ] Version number correct

### macOS
- [ ] `.app` bundle created in `dist/`
- [ ] `.dmg` file created (if on macOS)
- [ ] App launches from Applications
- [ ] Version number correct

---

## 📚 Scripts Reference

| Script | Platform | Purpose |
|--------|----------|---------|
| `scripts/build.py` | Windows | Builds EXE and installer |
| `scripts/build-deb.py` | Linux | Builds .deb package |
| `scripts/build-mac.py` | macOS | Builds .app bundle and .dmg |
| `scripts/installer.iss` | Windows | Inno Setup installer script |
| `setup.py` | Linux/macOS | Package setup configuration |

---

## 🚀 Development

### Run from Source
```bash
python main.py
# or
python3 main.py
```

The app will start on `http://127.0.0.1:8989`

---

**Last Updated**: October 2025  
**Maintained By**: Shakshuka Development Team
