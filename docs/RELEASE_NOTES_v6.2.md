# Release Notes - Version 6.2
**Release Date:** November 6, 2025  
**Build:** 1

## Overview
This release focuses on fixing critical UI/UX issues with task view management and resolving the version build system so version numbers properly increment with each build.

---

## 🎯 Major Features & Fixes

### 1. ✅ Task View Filter Preservation
**Issue:** When deleting a task, the UI was automatically switching to the "active" view regardless of which filter (completed, expired, active) you were in.

**Fix:** 
- Modified `deleteTask()` in both `app.js` and `tasks.js`
- Now captures current filter state before deletion
- Re-applies the same filter after deletion
- Users stay in their current view when managing tasks

**Files Changed:**
- `assets/static/js/app.js` (lines 1876-1878)
- `assets/static/js/tasks.js` (lines 150-162)

**Impact:** Better UX - no unexpected view switching while working with tasks

---

### 2. ✅ New Task Creation View Switching
**Issue:** When creating a new task from any view, it wasn't switching to the "active" view where the new task would be visible.

**Fix:**
- Added `setActiveFilter('active')` call after task creation
- Passes filter parameter explicitly to `renderTasks('active')`
- Users immediately see their newly created task

**File Changed:**
- `assets/static/js/app.js` (lines 1779-1781)

**Impact:** Better discoverability - users can immediately see newly created tasks

---

### 3. ✅ Customized Empty State Messages
**Issue:** Empty state message was generic "No tasks found" for all filter types.

**Fix:**
- Added conditional logic to customize messages per filter:
  - **Expired View:** "Yay! No missed tasks" with check-circle icon
  - **Active View:** "No active tasks" with inbox icon
  - **Completed View:** "No completed tasks" with clipboard icon

**File Changed:**
- `assets/static/js/app.js` (lines 1985-2012)

**Impact:** Better user feedback - contextual messages for each view

---

### 4. ✅ Version Build System Fixed
**Issue:** Inno Setup installer version numbers were stuck at 6.1 - build numbers weren't incrementing.

**Root Cause:**
- Version was hardcoded in `scripts/installer.iss` (line 5)
- Build script only updated `MyAppVersion` but missed:
  - `VersionInfoVersion`
  - `VersionInfoProductVersion`

**Fix:**
- Enhanced `update_installer_script()` function in `scripts/build.py`
- Now updates all three version fields
- Properly formats version with build number (e.g., "6.2.0.1")
- Added detailed logging for build transparency

**File Changed:**
- `scripts/build.py` (lines 235-271)

**Impact:** 
- Version numbers now increment properly with each build
- Windows can detect version updates correctly
- Build process is now transparent with detailed logging

**Before Build:**
```json
{
  "version": "6.1",
  "build": "6"
}
```

**After Build:**
- Installer: `Shakshuka-Setup-v6.2.exe`
- Internal version: `6.2.0.1`
- Windows File Properties shows: `6.2.0.1`

---

### 5. ✅ Code Cleanup
**Removed:**
- Unused `get_timezone_aware_time()` function in `src/app.py`
- Added comment documenting app uses local time (datetime.now())

**File Changed:**
- `src/app.py` (lines 1027-1028)

**Impact:** Cleaner codebase, removed dead code

---

## 📋 Technical Details

### Filter Preservation Implementation
```javascript
// In deleteTask()
const currentFilter = (AppState && AppState.get) ? AppState.get('currentFilter') || 'active' : 'active';
const currentPage = (AppState && AppState.get) ? AppState.get('currentPage') : 'tasks';

// After deletion, re-apply filter
if (currentPage === 'tasks') {
    if (typeof setActiveFilter === 'function') setActiveFilter(currentFilter);
    if (typeof renderTasks === 'function') renderTasks(currentFilter);
}
```

### Version Update in Build Script
```python
# Parses version and builds full version string
version_parts = version.split('.')
while len(version_parts) < 3:
    version_parts.append('0')
full_version = f"{'.'.join(version_parts)}.{build}"

# Updates all Inno Setup version fields
content = re.sub(r'VersionInfoVersion=.*', f'VersionInfoVersion={full_version}', content)
content = re.sub(r'VersionInfoProductVersion=.*', f'VersionInfoProductVersion={full_version}', content)
```

---

## 🚀 How to Build Next Version

1. **Update `config/version.json`:**
   ```json
   {
     "version": "6.3",
     "build": "1"
   }
   ```

2. **Run build:**
   ```powershell
   python scripts/build.py
   ```

3. **Verify:**
   - Check installer filename: `Shakshuka-Setup-v6.3.exe`
   - Right-click → Properties → Details
   - File version should show: `6.3.0.1`

---

## ✅ Testing Checklist

- [x] Task deletion preserves current filter
- [x] New task creation switches to active view
- [x] Empty state messages are contextual
- [x] Version increments properly in builds
- [x] Inno Setup script updates correctly
- [x] Changelog updated with all changes
- [x] Build logging shows version updates

---

## 📚 Files Modified in This Release

1. `assets/static/js/app.js` - Task view management
2. `assets/static/js/tasks.js` - Filter preservation
3. `scripts/build.py` - Version build system
4. `src/app.py` - Code cleanup
5. `config/version.json` - Version bump
6. `config/changelog.txt` - Changelog entry

---

## 🔄 Backwards Compatibility

✅ **Fully Backwards Compatible** - No breaking changes

All changes are additive or fixes to existing functionality. No API changes, no database schema changes.

---

## 📝 Next Planned Features

- [ ] Timezone-aware scheduling
- [ ] Advanced filter options
- [ ] Task templates
- [ ] Recurring tasks
- [ ] Team collaboration features

---

## 🙏 Thank You

Thanks for using Shakshuka! We're continuously improving the application to provide the best productivity experience.

For bugs or feature requests, visit: https://github.com/shakshuka-python
