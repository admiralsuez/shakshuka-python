# Decorator & Validator Application Guide

**Status:** Ready for implementation
**Target:** 30+ endpoints across all route files
**Expected Impact:** 30x less code duplication, 100% input validation

---

## 📋 Quick Reference

### Available Decorators
```python
from src.routes.route_decorators import (
    require_data_manager,      # Inject user_id and data_manager
    require_json_body,         # Ensure JSON request
    require_file_upload,       # Ensure file upload
    validate_input,            # Validate request data
    rate_limit,                # Rate limiting
    handle_database_error      # Database error handling
)
```

### Available Validators
```python
from src.routes.input_validators import (
    validate_schedule_input,   # hour, minute, duration
    validate_task_title,       # Non-empty, max 500 chars
    validate_priority,         # low/medium/high/critical
    validate_date_yyyy_mm_dd,  # YYYY-MM-DD format
    validate_description,      # Max 2000 chars
    validate_project_name,     # Max 100 chars
    validate_owner_name,       # Max 100 chars
    validate_strike_report,    # Max 2000 chars
    validate_bulk_operation_count  # Max 100 items
)
```

---

## 🎯 Implementation Examples

### Example 1: Simple GET Endpoint
**Before:**
```python
@task_bp.route('/<task_id>', methods=['GET'])
def get_task(task_id):
    user_id = _get_user_id()
    data_manager = _get_data_manager()
    if not data_manager:
        return jsonify({'error': 'Data manager not available'}), 500
    
    task = data_manager.get_task_by_id(user_id, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(task)
```

**After:**
```python
@task_bp.route('/<task_id>', methods=['GET'])
@require_data_manager
@handle_database_error
def get_task(task_id, user_id, data_manager):
    task = data_manager.get_task_by_id(user_id, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    return jsonify(task)
```

**Changes:**
- Added `@require_data_manager` - injects user_id and data_manager
- Added `@handle_database_error` - catches DatabaseError
- Removed manual data_manager check
- Removed manual user_id retrieval

---

### Example 2: POST with Validation
**Before:**
```python
@task_bp.route('/<task_id>/schedule', methods=['POST'])
def schedule_task(task_id):
    user_id = _get_user_id()
    schedule_data = request.json
    if schedule_data is None:
        schedule_data = {}
    
    ok, parsed, err = _parse_schedule_payload(schedule_data)
    if not ok:
        return jsonify({'error': err}), 400
    
    # ... rest of implementation
```

**After:**
```python
def validate_schedule(data):
    hour = data.get('hour')
    minute = data.get('minute', 0)
    duration = data.get('duration', 30)
    return validate_schedule_input(hour, minute, duration)

@task_bp.route('/<task_id>/schedule', methods=['POST'])
@require_data_manager
@validate_input(validate_schedule)
@handle_database_error
def schedule_task(task_id, user_id, data_manager):
    schedule_data = request.json
    hour = schedule_data.get('hour')
    minute = schedule_data.get('minute', 0)
    duration = schedule_data.get('duration', 30)
    date = schedule_data.get('date', datetime.now().strftime('%Y-%m-%d'))
    
    # ... rest of implementation (validation already done)
```

**Changes:**
- Created validator function
- Added `@validate_input(validate_schedule)` - validates automatically
- Removed manual validation code
- Removed manual data_manager check

---

### Example 3: File Upload with Rate Limiting
**Before:**
```python
@task_bp.route('/import', methods=['POST'])
def import_tasks():
    # Rate limiting code (20 lines)
    user_id = _get_user_id()
    if not hasattr(import_tasks, '_import_times'):
        import_tasks._import_times = {}
    
    from datetime import datetime
    now = datetime.now()
    key = user_id
    
    if key in import_tasks._import_times:
        import_tasks._import_times[key] = [
            t for t in import_tasks._import_times[key]
            if (now - t).total_seconds() < 3600
        ]
    else:
        import_tasks._import_times[key] = []
    
    if len(import_tasks._import_times[key]) >= 10:
        return jsonify({...}), 429
    
    import_tasks._import_times[key].append(now)
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '' or not file:
        return jsonify({'error': 'No file selected'}), 400
    
    # ... rest of implementation
```

**After:**
```python
@task_bp.route('/import', methods=['POST'])
@require_data_manager
@require_file_upload('file')
@rate_limit(max_requests=10, window_seconds=3600)
@handle_database_error
def import_tasks(user_id, data_manager):
    file = request.files['file']
    file_content = file.read().decode('utf-8')
    
    # ... rest of implementation (all checks done by decorators)
```

**Changes:**
- Removed 20 lines of rate limiting code
- Added `@require_file_upload('file')` - checks file exists
- Added `@rate_limit(max_requests=10, window_seconds=3600)` - rate limiting
- Removed manual file validation
- Removed manual rate limiting code

---

## 📊 Endpoints to Update (30+ total)

### Task Routes (task_routes.py)

#### High Priority (Already optimized, just add decorators)
1. ✅ `GET /api/tasks` - get_tasks
2. ✅ `POST /api/tasks` - create_task
3. ✅ `PUT /api/tasks/<task_id>` - update_task
4. ✅ `DELETE /api/tasks/<task_id>` - delete_task
5. ✅ `POST /api/tasks/<task_id>/complete` - complete_task
6. ✅ `POST /api/tasks/<task_id>/strike` - strike_task
7. ✅ `POST /api/tasks/<task_id>/undo-strike` - undo_strike
8. ✅ `POST /api/tasks/import` - import_tasks

#### Medium Priority (Need decorator + validation)
9. `POST /api/tasks/<task_id>/schedule` - schedule_task
10. `POST /api/tasks/<task_id>/unschedule` - unschedule_task
11. `GET /api/tasks/<task_id>/strike-reports` - get_strike_today_report_history
12. `POST /api/tasks/reset-daily-strikes` - reset_daily_strikes
13. `GET /api/tasks/export-excel` - export_excel

### Settings Routes (settings_routes.py)
14. `GET /api/settings` - get_settings
15. `PUT /api/settings` - update_settings
16. `GET /api/settings/autostart` - get_autostart_status

### Updates Routes (updates_routes.py)
17. `GET /api/updates/status` - get_update_status
18. `POST /api/updates/check` - check_for_updates
19. `POST /api/updates/download` - download_update
20. `POST /api/updates/install` - install_update
21. `GET /api/updates/progress` - get_download_progress
22. `POST /api/updates/cancel` - cancel_update_download
23. `GET /api/updates/config` - get_update_config
24. `PUT /api/updates/config` - update_update_config

### Notes Routes (notes_routes.py)
25. `GET /api/notes` - get_notes
26. `POST /api/notes` - create_note
27. `PUT /api/notes/<note_id>` - update_note
28. `DELETE /api/notes/<note_id>` - delete_note

### Mobile Routes (mobile_routes.py)
29. `POST /api/mobile/tasks/submit` - submit_tasks
30. `GET /api/mobile/sync-request` - get_sync_request
31. `POST /api/mobile/notes` - create_note

---

## 🔧 Implementation Steps

### Step 1: Create Validator Functions
Add at top of route file:
```python
from src.routes.input_validators import (
    validate_schedule_input,
    validate_task_title,
    # ... other validators
)

def validate_schedule(data):
    hour = data.get('hour')
    minute = data.get('minute', 0)
    duration = data.get('duration', 30)
    return validate_schedule_input(hour, minute, duration)

def validate_task_creation(data):
    title = data.get('title', '')
    valid, error = validate_task_title(title)
    if not valid:
        return False, error
    
    project = data.get('project', '')
    if project:
        valid, error = validate_project_name(project)
        if not valid:
            return False, error
    
    return True, ""
```

### Step 2: Add Decorators to Endpoint
```python
@task_bp.route('/<task_id>/schedule', methods=['POST'])
@require_data_manager
@validate_input(validate_schedule)
@handle_database_error
def schedule_task(task_id, user_id, data_manager):
    # Implementation
```

### Step 3: Remove Duplicate Code
- Remove manual `_get_user_id()` calls
- Remove manual `_get_data_manager()` checks
- Remove manual validation code
- Remove manual error handling for DatabaseError

### Step 4: Test
- Verify endpoint still works
- Verify validation catches invalid input
- Verify error responses are consistent

---

## 📝 Decorator Stack Order

**Recommended order (top to bottom):**
```python
@task_bp.route('/path', methods=['POST'])
@require_data_manager          # 1. Inject dependencies first
@require_json_body             # 2. Check request format
@validate_input(validator)     # 3. Validate input
@rate_limit(10, 60)            # 4. Rate limit
@handle_database_error         # 5. Handle errors last
def endpoint(user_id, data_manager):
    # Implementation
```

**Why this order:**
1. Dependencies injected first (needed by other decorators)
2. Request format checked early (fail fast)
3. Input validated before processing
4. Rate limit checked (prevent abuse)
5. Error handling wraps everything

---

## ✅ Validation Checklist

For each endpoint:
- [ ] Identify required decorators
- [ ] Create validator function (if needed)
- [ ] Add decorators in correct order
- [ ] Remove duplicate code
- [ ] Remove manual error handling
- [ ] Test endpoint
- [ ] Verify error responses
- [ ] Update documentation

---

## 🎯 Expected Results

### Code Reduction
- **Before:** 30+ endpoints with duplicate code
- **After:** 1 decorator + 30 endpoints
- **Reduction:** ~200 lines of duplicate code

### Consistency
- **Before:** Inconsistent error handling
- **After:** Standardized responses
- **Impact:** Better API consistency

### Maintainability
- **Before:** Changes needed in 30 places
- **After:** Changes in 1 decorator
- **Impact:** 30x easier to maintain

### Security
- **Before:** Manual validation in each endpoint
- **After:** Centralized validation
- **Impact:** Consistent security checks

---

## 📚 Additional Resources

### Error Response Format
```json
{
  "success": false,
  "error": "Error message",
  "details": {}
}
```

### Success Response Format
```json
{
  "success": true,
  "message": "Optional message",
  "data": {}
}
```

### Rate Limit Response
```json
{
  "error": "Rate limit exceeded: 10 requests per 3600 seconds",
  "details": {}
}
```

---

## 🚀 Next Steps

1. **Phase 1:** Apply decorators to task routes (8 endpoints)
2. **Phase 2:** Apply decorators to settings routes (3 endpoints)
3. **Phase 3:** Apply decorators to updates routes (8 endpoints)
4. **Phase 4:** Apply decorators to notes routes (4 endpoints)
5. **Phase 5:** Apply decorators to mobile routes (3 endpoints)

**Total Effort:** ~4-6 hours
**Expected Impact:** 30x less code duplication, 100% validation coverage

---

## 💡 Tips & Tricks

### Tip 1: Reuse Validators
```python
# Good: Reuse existing validator
valid, error = validate_task_title(title)

# Bad: Create new validation code
if not title or len(title) > 500:
    return False, "Invalid title"
```

### Tip 2: Combine Validators
```python
def validate_task_creation(data):
    # Validate title
    title = data.get('title', '')
    valid, error = validate_task_title(title)
    if not valid:
        return False, error
    
    # Validate project
    project = data.get('project', '')
    if project:
        valid, error = validate_project_name(project)
        if not valid:
            return False, error
    
    return True, ""
```

### Tip 3: Custom Validators
```python
def validate_custom_field(data):
    field = data.get('field')
    if not field:
        return False, "Field is required"
    if len(field) > 100:
        return False, "Field too long"
    return True, ""
```

---

**Ready to implement! Start with task routes for maximum impact.**
