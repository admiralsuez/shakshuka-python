# Build Instructions - Shakshuka

## Current Status
- Version: 6.2
- Build: 4
- Location: `config/version.json`

## Building with Auto-Increment

The build system is designed to auto-increment the build number when you run a build. Here's how:

### Option 1: Using Python Build Script (Recommended)

The `scripts/build.py` script automatically handles build number incrementation:

```bash
python scripts/build.py
```

This will:
1. ✅ Read current version from `config/version.json` (6.2, build 4)
2. ✅ Increment build number to 5
3. ✅ Update `config/version.json` with new build number
4. ✅ Update `scripts/installer.iss` with version info (6.2.0.5)
5. ✅ Build PyInstaller executable
6. ✅ Build Inno Setup installer
7. ✅ Generate build report

### Option 2: Manual Build Number Increment

If you want to manually increment before building:

```python
# In Python shell or script:
import json
from datetime import datetime

# Read current version
with open('config/version.json', 'r') as f:
    version_data = json.load(f)

# Increment build number
current_build = int(version_data.get('build', 0))
version_data['build'] = str(current_build + 1)
version_data['release_date'] = datetime.now().isoformat()

# Write back
with open('config/version.json', 'w') as f:
    json.dump(version_data, f, indent=2)

print(f"Build number incremented: {current_build} -> {current_build + 1}")
```

### Option 3: Manual Edit

Edit `config/version.json` directly:

```json
{
  "version": "6.2",
  "build": "5",
  "release_date": "2025-11-06T18:38:50Z",
  "update_channel": "stable",
  "build_notes": "Your notes here..."
}
```

## Verification

After building, verify the version:

1. **Check version.json:**
   ```bash
   cat config/version.json
   ```
   Should show `"build": "5"` (or next increment)

2. **Check installer script:**
   ```bash
   grep "VersionInfoVersion" scripts/installer.iss
   grep "VersionInfoProductVersion" scripts/installer.iss
   ```
   Should show `6.2.0.5` (matching your new build number)

3. **Check in the app:**
   - Run the executable or installer
   - Settings page should show v6.2.5 (version.build format)

## Build Number Increment Sequence

Expected sequence:
```
Build 1 → version.json: 6.2, build: 1 → Installer: 6.2.0.1
Build 2 → version.json: 6.2, build: 2 → Installer: 6.2.0.2
Build 3 → version.json: 6.2, build: 3 → Installer: 6.2.0.3
Build 4 → version.json: 6.2, build: 4 → Installer: 6.2.0.4 ← CURRENT
Build 5 → version.json: 6.2, build: 5 → Installer: 6.2.0.5 ← NEXT
```

## Troubleshooting

### Build stuck at 6.2?

**Issue:** Build number not incrementing  
**Solution:** 
1. Check `config/version.json` - ensure it has a numeric `build` field
2. Run `python scripts/build.py` - it should auto-increment
3. If using Inno Setup GUI directly, the script won't auto-increment

### Installer version wrong?

**Issue:** Installer shows old version (e.g., 6.2.0.4)  
**Solution:**
1. Check if `scripts/build.py` ran the `update_installer_script()` function
2. Manually verify `scripts/installer.iss` has correct VersionInfoVersion
3. The fix in build.py (multiline regex) now handles this correctly

### Version not showing in app?

**Issue:** App shows old version despite new build  
**Solution:**
1. Make sure you're running the newly built executable, not cached version
2. Check that `config/version.json` is included in the PyInstaller bundle
3. In frozen mode, app reads from bundled version.json, not file system

## Key Files

- **Version source:** `config/version.json`
- **Build script:** `scripts/build.py` (handles auto-increment)
- **Installer template:** `scripts/installer.iss` (gets updated by build.py)
- **Version display in app:** `src/utils/helpers.py` → `get_app_version()`

## Next Build

To build version 6.2 build 5:

```bash
# Option 1: Auto-increment via script (RECOMMENDED)
python scripts/build.py

# Option 2: Manual increment then build
# 1. Edit config/version.json, change build from 4 to 5
# 2. Run: python scripts/build.py
```

Both approaches will:
✅ Update version.json
✅ Update installer.iss
✅ Build executable
✅ Build installer

---

**Last Updated:** November 6, 2025  
**Current Build:** 6.2.0.4  
**Next Build:** 6.2.0.5 (when you run build.py)
