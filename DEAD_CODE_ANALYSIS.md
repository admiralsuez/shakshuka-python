# Dead Code Analysis Report

## Summary
This report identifies unused functions and dead code in the Shakshuka codebase.

---

## Backend (Python)

### 1. **UpdateManager - Deprecated Daemon Thread Methods**
**File:** `src/update_manager.py`

#### Removed:
- ❌ `start_auto_update_check()` - **REMOVED** (was calling non-existent `_auto_update_check_worker`)
  - **Reason:** Replaced by scheduler-based `_setup_auto_update_scheduler()`
  - **Status:** Fixed in latest commit

#### Still Present (Deprecated):
- ⚠️ `stop_auto_update_check()` - **DEPRECATED** (kept for backward compatibility)
  - **Reason:** No longer used; scheduler handles lifecycle
  - **Recommendation:** Can be removed in future cleanup

#### Attributes (Still Used):
- `self.update_check_thread` - Used in `stop_auto_update_check()`
- `self.update_check_enabled` - Used in `stop_auto_update_check()`

---

## Frontend (JavaScript)

### 1. **Duplicate Function Definition**
**File:** `assets/static/js/pages/tasks.js`

#### Removed:
- ❌ `syncStrikeClassesFromState()` (second definition at line 1350) - **REMOVED**
  - **Reason:** Duplicate of function defined at line 745
  - **Status:** Fixed in latest commit

#### Kept:
- ✅ `syncStrikeClassesFromState()` (first definition at line 745)
  - **Usage:** Exported to window, called after daily reset

---

### 2. **Unused Utility Functions**
**File:** `assets/static/js/utils/utils.js`

#### Potentially Unused:
- ⚠️ `throttle(func, limit)` - **DEFINED BUT NOT CALLED**
  - **Location:** Lines 398-409
  - **Purpose:** Throttle function calls
  - **Usage:** No calls found in codebase
  - **Recommendation:** Remove if not needed for future features

- ⚠️ `generateId()` - **DEFINED BUT NOT CALLED**
  - **Location:** Lines 412-414
  - **Purpose:** Generate unique IDs
  - **Usage:** No calls found in codebase
  - **Recommendation:** Remove if not needed for future features

---

## Summary Table

| Category | Item | Status | Action |
|----------|------|--------|--------|
| Python | `start_auto_update_check()` | ❌ Removed | Fixed |
| Python | `stop_auto_update_check()` | ⚠️ Deprecated | Keep for now |
| JavaScript | `syncStrikeClassesFromState()` duplicate | ❌ Removed | Fixed |
| JavaScript | `throttle()` | ⚠️ Unused | Consider removing |
| JavaScript | `generateId()` | ⚠️ Unused | Consider removing |

---

## Recommendations

### High Priority (Already Fixed)
1. ✅ Removed `start_auto_update_check()` - was calling non-existent method
2. ✅ Removed duplicate `syncStrikeClassesFromState()` function

### Medium Priority (Optional Cleanup)
1. Remove `throttle()` if not planned for future use
2. Remove `generateId()` if not planned for future use
3. Remove deprecated `stop_auto_update_check()` in next major version

### Low Priority
- Monitor for other unused code as codebase evolves
- Consider using a linter (ESLint for JS, Pylint for Python) for automated detection

---

## Testing Notes

After these changes:
- ✅ UpdateManager initialization now uses scheduler-based methods
- ✅ No duplicate function definitions
- ✅ All exported functions have clear usage patterns
- ✅ Startup warning about `_auto_update_check_worker` is resolved
