# 🍳 Shakshuka - Build Guide

Complete guide for building Shakshuka for Windows, Linux, and macOS.

---

## Recent Work Summary (desktop v26.1 · companion v1.5.0)

This section documents the most recent fixes and features so a new contributor can quickly understand what changed, where to look, and how to verify behavior.

### What changed

#### Two-way companion app sync (the core feature)
Previously the desktop Sync button could only pull tasks that the phone had already manually pushed. Now the flow is fully automatic:

1. **Desktop → phone signal**: when the desktop Sync button finds an empty inbox it calls `POST /api/mobile/request-sync` (local-only) which sets an in-memory one-shot flag, then shows *"Asking phone to send tasks…"*
2. **Phone polls for the signal**: the companion app polls `GET /api/mobile/sync-request` (bearer-token auth) hourly and also 1 minute after the *last* task is added (debounced). Reading the flag atomically clears it.
3. **Auto-upload**: when the phone detects a pending request it silently calls `uploadTasksAndNotes()` for all local tasks/notes and shows a snackbar. No manual "Send to PC" tap required.
4. **Desktop shows notification**: after the user approves the imported tasks in the sync modal, an entry appears in the desktop Notifications bell (daily-reset-log-modal) showing the device name, item count, time, and task titles.

#### Skip now unblocks the queue
The Sync modal Skip button previously only hid the dialog; the submission stayed `pending` and permanently blocked newer ones. It now calls `POST /api/mobile/inbox/<id>/reject` on the backend so the queue advances.

### Key files touched

- **Backend (Python)**
  - `src/routes/mobile_routes.py` — new `POST /api/mobile/request-sync` and `GET /api/mobile/sync-request` endpoints; `_sync_requested` in-memory dict (ephemeral by design)
- **Desktop JS**
  - `assets/static/js/app/companion-sync.js` — calls request-sync when inbox empty; passes `payload` to `importCompanionTasks` and calls `DailyResetLog.addCompanionSync()` on success
  - `assets/static/js/app/daily-reset-log.js` — new `latestCompanionSync` state, `renderCompanionSyncSection()`, updated `updateIndicator()`, exposed `window.DailyResetLog.addCompanionSync()` / `clearCompanionSync()`
- **Desktop HTML**
  - `assets/templates/partials/modals/daily_reset_log_modal.html` — added `#daily-reset-companion-sync` slot div
- **Companion app (Flutter/Dart)**
  - `shakshuka_companion/lib/services/api_service.dart` — new `checkSyncRequest()` method
  - `shakshuka_companion/lib/screens/home_screen.dart` — `_syncRequestTimer` (1 h periodic), `_taskAddedSyncTimer` (1 min debounce), `_startSyncRequestPolling()`, `_schedulePostAddSyncCheck()`, `_pollSyncRequest()`, `_autoUploadAllTasks()`
  - `shakshuka_companion/pubspec.yaml` — bumped to `1.5.0+15`
- **Changelogs**
  - `config/changelog.txt` — v26.1 entry
  - `home_screen.dart` changelog widget — v1.5.0 entry; version labels updated throughout

### How to verify (manual)

1. Pair the phone, add a new task on the phone, wait ≥ 1 minute (or press Sync immediately on desktop first to arm the flag).
2. Desktop Sync button should show *"Asking phone to send tasks…"* and then, after the phone auto-uploads (within ~1 min), the import modal should appear on the next Sync press.
3. Skip a pending submission in the import modal — confirm a subsequent Sync shows the next submission rather than the same one.
4. After approving a batch, open the desktop Notifications bell and confirm an entry listing the device, count, and task titles appears.

### No DB changes
The sync-request signal is intentionally in-memory (`_sync_requested` dict). All mobile tables (`mobile_devices`, `mobile_inbox`) were already created by migration 014 and require no schema changes.

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
