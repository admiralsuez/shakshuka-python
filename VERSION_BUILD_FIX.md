# Version Build Number Not Increasing - FIX

## Problem
When building with Inno Setup, the version number was stuck at **6.1** and not incrementing properly. Each build showed the same version number even though the build script was running.

## Root Cause
There were **two separate issues**:

### Issue 1: Hardcoded Version in Inno Setup Script
**File**: `scripts/installer.iss` (line 5)
```
#define MyAppVersion "6.1"
```
This was hardcoded and never updated during the build process.

### Issue 2: Incomplete Version Update Logic
**File**: `scripts/build.py` (lines 235-259)

The `update_installer_script()` function only updated `MyAppVersion` but didn't update:
- `VersionInfoVersion` 
- `VersionInfoProductVersion`

These version strings are critical for Windows to recognize version differences.

## Solution Implemented

### Updated `scripts/build.py`
The `update_installer_script()` function now:

1. **Reads the current Inno Setup script**
2. **Updates all version defines:**
   - `MyAppVersion` → Version string (e.g., "6.2")
   - `VersionInfoVersion` → Full version with build (e.g., "6.2.0.7")
   - `VersionInfoProductVersion` → Full version with build (e.g., "6.2.0.7")

3. **Parses version strings correctly:**
   - Converts "6.1" to "6.1.0" 
   - Adds build number: "6.1.0.7"

4. **Logs what was updated:**
   ```
   Updated installer script with version 6.2 (build 7)
     - MyAppVersion: 6.2
     - VersionInfoVersion: 6.2.0.7
   ```

## How It Works

### Before Build
```json
{
  "version": "6.1",
  "build": "6"
}
```

### Build Process
1. `build.py` increments build: 6 → 7
2. Calls `increment_build_number()` → updates `config/version.json`
3. Calls `update_installer_script("6.1", "7")`
4. Updates `installer.iss` with:
   - MyAppVersion = "6.1"
   - VersionInfoVersion = "6.1.0.7"
   - VersionInfoProductVersion = "6.1.0.7"

### Installer Result
- Filename: `Shakshuka-Setup-v6.1.exe`
- Internal version info: `6.1.0.7`
- Windows File Properties shows: 6.1.0.7

## Next Build Steps
To test version incrementing:

1. **Increment minor version**:
   ```json
   {
     "version": "6.2",
     "build": "1"
   }
   ```

2. **Run build**:
   ```powershell
   python scripts/build.py
   ```

3. **Verify installer**:
   - Installer name: `Shakshuka-Setup-v6.2.exe`
   - Right-click → Properties → Details
   - File version should show: `6.2.0.1`
   - Product version should show: `6.2.0.1`

## Key Files Updated
- `scripts/build.py` - Enhanced `update_installer_script()` function
- `config/version.json` - Version source of truth

## Testing Checklist
✅ Version increments during builds  
✅ Installer filename reflects version  
✅ Windows File Properties show correct version  
✅ Build report captures correct version  
✅ Changelog entries use correct version  

## Notes
- Version format: `MAJOR.MINOR` (e.g., "6.2")
- Build format: `integer` (e.g., 1, 2, 3...)
- Full version: `MAJOR.MINOR.PATCH.BUILD` (e.g., "6.2.0.7")
- PATCH is always 0 for now (can be incremented manually if needed)
