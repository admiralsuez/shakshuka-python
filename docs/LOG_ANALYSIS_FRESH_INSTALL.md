# Fresh Installation Log Analysis - October 28, 2025

**Log File:** `shakshuka.log` from fresh installation on new computer  
**Date:** October 28, 2025, 14:32-14:33 UTC  
**Installation Type:** New/First-time setup  

---

## Executive Summary

Fresh installations encounter **4 critical issues**:

| Issue | Endpoint | Status | Severity | Impact |
|-------|----------|--------|----------|--------|
| Task Creation | POST /api/tasks | ✅ FIXED | Critical | **Blocks all task operations** |
| Updates Config | GET /api/updates/config | ⚠️ TODO | High | Prevents update checking |
| Account Endpoint | GET /api/account | ⚠️ TODO | Medium | Account settings missing |
| Settings Update | PUT /api/settings | ⚠️ TODO | Medium | Settings can't be saved |

---

## Issue 1: Task Creation Error ✅ FIXED

### Error Details
```
ERROR - Incorrect number of bindings supplied. The current statement uses 19, and there are 21 supplied.
Failed to create task for user default_user
POST /api/tasks HTTP/1.1 - 500
```

**Log Lines:** 85-93

### Root Cause
- SQL INSERT statement had only 19 column placeholders
- `_task_dict_to_row()` returns 21 values
- Missing columns: `scheduled_minute`, `scheduled_date`

### Solution Applied ✅
Updated 4 INSERT statements in `src/sqlite_data_manager.py`:
- Line 940-945: `create_task_for_user()`
- Line 884-889: `save_tasks()` backup
- Line 1125-1130: `update_task_for_user()` backup
- Line 1198-1203: `delete_task_for_user()` backup

**See:** `docs/BUG_FIX_TASK_CREATION.md` for details

---

## Issue 2: Updates Config Endpoint 500 Error ⚠️ TODO

### Error Details
```
GET /api/updates/config HTTP/1.1 - 500
```

**Log Lines:** 79, 84, 109  
**Frequency:** 3 occurrences in ~27 seconds

### Code Analysis
```python
# src/app.py, line 2658
@app.route('/api/updates/config', methods=['GET'])
@require_auth
def get_update_config():
    """Get update configuration"""
    if not app_context.update_manager:
        return jsonify({'error': 'Update manager not initialized'}), 500
    
    return jsonify(app_context.update_manager.update_config)  # ← PROBLEM
```

### Potential Causes
1. **Missing error handling:** No try-except block wrapping the jsonify call
2. **update_config might be None or not serializable:** The update_config attribute might contain non-JSON-serializable objects
3. **UpdateManager initialization issues:** `app_context.update_manager` might exist but have incomplete initialization

### Investigation Needed
- Check `src/update_manager.py` for `update_config` structure
- Verify `_load_update_config()` returns valid JSON-serializable data
- Add error handling and logging

### Recommended Fix
```python
@app.route('/api/updates/config', methods=['GET'])
@require_auth
def get_update_config():
    """Get update configuration"""
    try:
        if not app_context.update_manager:
            return jsonify({'error': 'Update manager not initialized'}), 500
        
        if not hasattr(app_context.update_manager, 'update_config'):
            logger.error("update_manager missing update_config attribute")
            return jsonify({'error': 'Update config not available'}), 500
        
        config = app_context.update_manager.update_config
        if config is None:
            logger.warning("update_config is None, returning default")
            config = {
                "auto_check_enabled": True,
                "check_interval_hours": 24,
                "auto_install_enabled": False,
                "backup_before_update": True,
                "update_channel": "stable"
            }
        
        return jsonify(config)
    except Exception as e:
        logger.error(f"Error getting update config: {e}", exc_info=True)
        return jsonify({'error': 'Failed to get update configuration'}), 500
```

---

## Issue 3: Account Endpoint 404 Error ⚠️ TODO

### Error Details
```
GET /api/account HTTP/1.1 - 404
```

**Log Line:** 110

### Problem
The `/api/account` endpoint **does not exist** in the backend, but the frontend tries to call it.

### Code Evidence
```javascript
// assets/static/js/app.js, line 688
async function loadAccountSettings() {
    try {
        const response = await Utils.makeAuthenticatedRequest('/api/account');  // ← 404!
        // ...
    }
}
```

### Frontend Expectation
The frontend expects an `/api/account` endpoint that returns:
```json
{
    "username": "string",
    "created_at": "ISO datetime",
    "last_login": "ISO datetime"
}
```

### Recommended Fix
Create the missing endpoint in `src/app.py`:

```python
@app.route('/api/account', methods=['GET'])
@require_auth
def get_account_info():
    """Get current user account information"""
    try:
        user_id = get_user_id()
        
        # Load user from database
        user = app_context.user_manager.get_user(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({
            'username': user.get('username', user_id),
            'created_at': user.get('created_at'),
            'last_login': user.get('last_login'),
            'id': user_id
        })
    except Exception as e:
        logger.error(f"Error getting account info for user {get_user_id()}: {e}")
        return jsonify({'error': 'Failed to get account information'}), 500
```

---

## Issue 4: Settings Update 500 Error ⚠️ TODO

### Error Details
```
PUT /api/settings HTTP/1.1 - 500
```

**Log Line:** 112

### Code Analysis
The endpoint exists (`src/app.py`, line 2229) with comprehensive error handling, but still returns 500.

```python
@app.route('/api/settings', methods=['PUT'])
@require_auth
def update_settings():
    """Update application settings..."""
    user_id = get_user_id()
    
    # ... extensive validation code ...
    
    try:
        # ... settings update logic ...
        return jsonify(current_settings)
    except Exception as e:
        logger.error(f"Error updating settings for user {user_id}: {e}")
        return jsonify({'error': 'Failed to update settings'}), 500
```

### Likely Causes (Need Log Details)
1. **Database save failure:** `app_context.data_manager.save_settings()` failing after 3 retries
2. **Autostart enable/disable failure:** Lines 2341-2355 might be throwing exceptions on Windows
3. **Validation error:** One of the settings might fail validation

### Missing Information
- **No detailed error message in logs** - The actual exception is not logged with details
- **Autostart operation on Windows:** Likely cause on fresh install

### Recommended Diagnostic Fix

Add more detailed logging to `src/app.py` line 2229-2388:

```python
except Exception as e:
    logger.error(f"Error updating settings for user {user_id}: {e}", exc_info=True)
    import traceback
    logger.error(f"Full traceback: {traceback.format_exc()}")
    return jsonify({'error': 'Failed to update settings', 'details': str(e)}), 500
```

Also check lines 2340-2355 (autostart handling):
```python
if 'autostart' in settings_data:
    autostart_value = settings_data['autostart']
    if isinstance(autostart_value, bool):
        try:
            if autostart_value:
                # ... get path ...
                app_context.autostart_manager.enable_autostart(exe_path)
            else:
                app_context.autostart_manager.disable_autostart()
            autostart_updated = True
        except Exception as e:
            logger.error(f"Failed to update autostart setting: {e}")  # ← This error is SWALLOWED
            # If autostart fails, the entire settings update might fail later
```

---

## Summary of Issues

### Critical (Task Creation) ✅ FIXED
- **Status:** RESOLVED with commit fixing SQL bindings
- **Impact:** Now users can create tasks on fresh installations

### High Priority (Updates Config)
- **Status:** Needs investigation and error handling
- **Impact:** Update checking fails silently
- **Effort:** Low - Add try-catch and logging

### Medium Priority (Account Info)
- **Status:** Endpoint completely missing
- **Impact:** Account settings tab shows errors in console
- **Effort:** Medium - Create new endpoint + test

### Medium Priority (Settings Update)
- **Status:** Has retry logic but still fails
- **Impact:** User preferences can't be persisted
- **Effort:** Medium - Add detailed diagnostics and autostart fix

---

## Recommended Action Plan

1. ✅ **Deploy Task Creation Fix** (Already done)
2. ⚠️ **Add error handling to `/api/updates/config`** (15 minutes)
3. ⚠️ **Create `/api/account` endpoint** (30 minutes)
4. ⚠️ **Improve settings update diagnostics** (30 minutes)
5. ✅ **Test fresh installation again** with all fixes

---

## Testing Notes

For fresh installation validation:
```
1. Install on new machine
2. Verify no 500 errors in console (F12)
3. Create a task → HTTP 200 ✓
4. Update settings → HTTP 200 ✓
5. Check account info loads → HTTP 200 ✓
6. Verify updates config loads → HTTP 200 ✓
```




