# Bug Fixes: Fresh Installation Issues

**Date Fixed:** October 28, 2025  
**Version:** v3.0.6  
**Severity:** Critical (Blocks fresh installations)  
**Status:** ✅ RESOLVED

This document covers **two critical bugs** found on fresh installations:

## Quick Summary

| Bug | Location | Issue | Fix |
|-----|----------|-------|-----|
| **#1** | `create_task_for_user()` | Missing 2 columns in INSERT (scheduled_minute, scheduled_date) | Added missing columns to match 21-value tuple |
| **#2** | `save_settings_for_user()` | Commit only executed in else block | Fixed indentation so commit executes for both paths |

**Files Modified:** `src/sqlite_data_manager.py`  
**Result:** Fresh installations now fully functional ✅

---

## Bug #1: Task Creation SQL Parameter Binding Mismatch

### Problem

When creating tasks on a fresh installation (new computer), the application was throwing a critical error:

```
ERROR - Incorrect number of bindings supplied. The current statement uses 19, and there are 21 supplied.
```

This prevented any task creation, resulting in HTTP 500 errors when users tried to create their first task.

### Affected Operations
- `create_task_for_user()` - **PRIMARY ISSUE** (line 940-945)
- `save_tasks()` backup restoration (line 884-889)
- `update_task_for_user()` backup restoration (line 1125-1130)
- `delete_task_for_user()` backup restoration (line 1198-1203)

### Error Log Example
```
2025-10-28 14:32:50,608 - src.sqlite_data_manager.SQLiteDataManager - ERROR - Transaction failed for user default_user, attempt 1: Incorrect number of bindings supplied. The current statement uses 19, and there are 21 supplied.
2025-10-28 14:32:50,938 - src.app - ERROR - Failed to create task for user default_user
2025-10-28 14:32:50,940 - werkzeug - INFO - 127.0.0.1 - - [28/Oct/2025 14:32:50] "POST /api/tasks HTTP/1.1" 500 -
```

---

## Root Cause Analysis

### The Mismatch
The `_task_dict_to_row()` helper method (lines 718-742) returns **21 values** when converting a task dictionary to a database row tuple:

```python
def _task_dict_to_row(self, task: Dict[str, Any], user_id: str) -> tuple:
    return (
        task['id'],                          # 1
        user_id,                             # 2
        task['title'],                       # 3
        task.get('description', ''),         # 4
        task.get('project', ''),             # 5
        task.get('priority', 'medium'),      # 6
        task.get('status', 'pending'),       # 7
        task.get('completed', False),        # 8
        task.get('completed_at'),            # 9
        task.get('due_date'),                # 10
        task.get('estimated_duration', 60),  # 11
        task.get('scheduled_hour'),          # 12
        task.get('scheduled_minute'),        # 13 ← MISSING
        task.get('scheduled_date'),          # 14 ← MISSING
        task.get('scheduled_duration'),      # 15
        task.get('struck_today', False),     # 16
        task.get('struck_date'),             # 17
        task.get('strike_report'),           # 18
        task.get('strike_count', 0),         # 19
        task.get('created_at', ...),         # 20
        task.get('updated_at', ...)          # 21
    )
```

However, the SQL INSERT statements were only expecting **19 columns**, missing:
- `scheduled_minute` (column 13)
- `scheduled_date` (column 14)

### Why It Occurred
The columns were added to the schema later to support task scheduling features, but the INSERT statements in several places weren't updated to match. This caused SQLite to reject the INSERT operations with a parameter count mismatch.

---

## Solution

Updated all four INSERT statements in `src/sqlite_data_manager.py` to include the missing columns.

### Before (19 columns, ❌ BROKEN):
```sql
INSERT INTO tasks (
    id, user_id, title, description, project, priority, status,
    completed, completed_at, due_date, estimated_duration, scheduled_hour,
    scheduled_duration, struck_today, struck_date, strike_report, strike_count,
    created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

### After (21 columns, ✅ FIXED):
```sql
INSERT INTO tasks (
    id, user_id, title, description, project, priority, status,
    completed, completed_at, due_date, estimated_duration, scheduled_hour,
    scheduled_minute, scheduled_date, scheduled_duration, struck_today, struck_date, strike_report, strike_count,
    created_at, updated_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
```

---

## Changes Made

| Location | Method | Status |
|----------|--------|--------|
| Lines 940-945 | `create_task_for_user()` | ✅ Fixed (PRIMARY ISSUE) |
| Lines 884-889 | `save_tasks()` - backup restoration | ✅ Fixed |
| Lines 1125-1130 | `update_task_for_user()` - backup restoration | ✅ Fixed |
| Lines 1198-1203 | `delete_task_for_user()` - backup restoration | ✅ Fixed |

**File Modified:** `src/sqlite_data_manager.py`

---

## Impact

This fix enables:
- ✅ Creating new tasks without errors
- ✅ Successful fresh installations on new computers
- ✅ Proper task scheduling with scheduled_minute and scheduled_date fields
- ✅ Backup restoration working correctly during failure recovery
- ✅ HTTP 200 responses for POST /api/tasks instead of HTTP 500

---

## Verification Steps

To verify the fix works correctly:

1. **Fresh Installation Test**
   - Start Shakshuka on a new computer
   - Verify database is initialized
   - Create a task via the UI
   - Confirm HTTP 200 response (not 500)

2. **Database Verification**
   ```sql
   SELECT scheduled_minute, scheduled_date 
   FROM tasks 
   LIMIT 1;
   ```
   Should return NULL or valid values, not error

3. **Log Verification**
   - No "Incorrect number of bindings supplied" errors
   - No "Transaction failed" errors during task creation
   - "Successfully created task" messages appear

---

## Related Issues

- **Previous Fix:** API Credentials Configuration (v3.0.0)
  - Different issue: Missing environment configuration
  - Bug #1: Database schema mismatch in code
  - Bug #2: Indentation error causing uncommitted transactions
  
- **Still Not Fixed (Not Related):**
  - Update check errors (GET /api/updates/config 500) - Requires separate investigation
  - Account endpoint 404 (GET /api/account) - Feature may not be implemented

---

## Bug #2: Settings Save Indentation Error

### Problem

When updating settings on a fresh installation, the application was returning a 500 error:

```
2025-10-28 14:33:02,410 - src.sqlite_data_manager.SQLiteDataManager - INFO - Successfully loaded settings for user default_user
2025-10-28 14:33:02,454 - werkzeug - INFO - 127.0.0.1 - - [28/Oct/2025 14:33:02] "PUT /api/settings HTTP/1.1" 500 -
```

This prevented users from changing any application settings (theme, notifications, autosave, etc.).

### Root Cause

**Indentation bug** in `save_settings_for_user()` method (lines 1480-1483):

```python
if table_exists:
    # Use new user_preferences table
    conn.execute('''
        INSERT OR REPLACE INTO user_preferences (...)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (...))
else:
    # Fallback to old settings table
    conn.execute('''
        INSERT OR REPLACE INTO settings (...)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (...))

# ❌ WRONG INDENTATION - These lines were indented too far (inside the else block)
    conn.commit()  
    self.logger.info(f"Successfully saved settings for user {user_id}")
    return True
```

**The Issue:**
- Lines 1481-1483 (`conn.commit()`, logger, `return True`) were indented inside the `else` block
- They only executed when the OLD `settings` table was used
- When the NEW `user_preferences` table existed (which it does on migrations), the INSERT would execute but **never commit**
- The function would fall through without returning and eventually return `False`, causing HTTP 500

### Why It Occurred

During database migration to the new `user_preferences` table schema, the code was updated to check which table exists and use the appropriate one. However, the commit logic was mistakenly left indented inside the `else` block instead of being placed after the if/else statement to execute for both cases.

### Solution

Fixed the indentation by moving lines 1481-1483 to the correct level - **after** the if/else block:

#### Before (❌ BROKEN):
```python
else:
    # Fallback to old settings table
    conn.execute('''...''', (...))

# These were wrongly indented inside the else block
    conn.commit()
    self.logger.info(f"Successfully saved settings for user {user_id}")
    return True
```

#### After (✅ FIXED):
```python
else:
    # Fallback to old settings table
    conn.execute('''...''', (...))

# Now correctly at the same level as the if/else, executes for both paths
conn.commit()
self.logger.info(f"Successfully saved settings for user {user_id}")
return True
```

### Changes Made

| Location | Method | Status |
|----------|--------|--------|
| Lines 1480-1483 | `save_settings_for_user()` | ✅ Fixed (Dedented commit/return) |

**File Modified:** `src/sqlite_data_manager.py`

### Impact

This fix enables:
- ✅ Saving settings successfully (HTTP 200 instead of 500)
- ✅ Users can change themes, notifications, autosave intervals
- ✅ Database commits properly for new `user_preferences` table
- ✅ Daily reset time changes work correctly
- ✅ Autostart toggle functionality works

---

## Combined Impact

Both fixes together restore full functionality for fresh installations:
- ✅ **Bug #1 Fix:** Users can create tasks
- ✅ **Bug #2 Fix:** Users can update settings
- ✅ Fresh installations now fully functional
- ✅ All CRUD operations work correctly
- ✅ No more HTTP 500 errors on core functionality

---

## Notes for Developers

### General Best Practices
- Always ensure INSERT/UPDATE statements match helper method return values
- Count parameters in SQL statements when schema columns are added
- Use code review to catch these mismatches before deployment
- Consider using ORM to reduce manual SQL maintenance

### Indentation-Specific
- **Always verify commit/return statements are at the correct indentation level**
- When adding if/else branches for table migrations, ensure cleanup code (commit, logging, return) is outside the conditional
- Use linters and formatters (black, pylint) to catch indentation issues
- Test both migration paths (old and new table schemas) during development

### Testing for Fresh Installations
- Always test on a clean database without existing schema
- Verify both task creation and settings updates work
- Check that migrations apply correctly
- Ensure all CRUD operations return proper HTTP status codes
