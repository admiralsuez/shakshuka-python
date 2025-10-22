# SHAKSHUKA PROJECT - COMPLETE SUMMARY & METHODS REFERENCE

## Executive Summary

**Shakshuka** is a production-ready, modern task management application with over **2800+ lines of Python Flask code**, beautiful glass-morphism UI, encrypted SQLite database, and Windows system integration.

### Key Metrics
- ✅ **Version:** 1.4.17 (Build 31) - October 22, 2025
- ✅ **Code Files:** 50+ (Python, JavaScript, HTML, CSS)
- ✅ **Main Backend:** 2,800 lines (src/app.py)
- ✅ **API Endpoints:** 40+ routes
- ✅ **Database:** SQLite with 4 tables, 5 indexes
- ✅ **UI Theme:** Modern glass-morphism with gradient backgrounds
- ✅ **Backend:** Python 3.8+, Flask 2.3.3
- ✅ **Frontend:** HTML5, CSS3, Vanilla JavaScript (ES6+)
- ✅ **Deployment:** Single standalone executable (PyInstaller)

---

## 🏗️ ARCHITECTURE BLUEPRINT

### High-Level System Design

```
┌─────────────────────────────────────────────────────────────┐
│                    USER BROWSER                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  index.html (SPA)                                    │   │
│  │  ├─ app.js (UI logic)                               │   │
│  │  ├─ auth.js (authentication)                        │   │
│  │  ├─ state.js (client state)                         │   │
│  │  ├─ utils.js (helpers)                              │   │
│  │  └─ api.js (HTTP calls)                             │   │
│  │                                                      │   │
│  │  CSS: style.css, tasks.css, responsive.css          │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
           ↓ HTTP/HTTPS (port 8989) ↑
┌─────────────────────────────────────────────────────────────┐
│              FLASK APPLICATION (main.py)                     │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ src/app.py                                           │   │
│  │ • 119+ functions                                     │   │
│  │ • 40+ API routes                                     │   │
│  │ • AppContext (centralized state)                     │   │
│  │ • Decorators: @require_auth, @require_csrf, etc.    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ MIDDLEWARE LAYER                                     │   │
│  │ • Rate Limiting (100 req/5 min per IP)              │   │
│  │ • CSRF Protection (15-min token expiry)             │   │
│  │ • Session Management (24-hour sessions)             │   │
│  │ • Security Headers                                  │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ SERVICE LAYER                                        │   │
│  │ • security_manager.py (input validation)            │   │
│  │ • user_manager.py (authentication)                  │   │
│  │ • update_manager.py (OTA updates)                   │   │
│  │ • monitoring.py (performance tracking)              │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ BACKGROUND THREADS                                  │   │
│  │ • auto_save_worker (30s interval)                   │   │
│  │ • scheduler_worker (daily resets)                   │   │
│  │ • system_tray (Windows integration)                 │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
           ↓ SQL Operations ↑
┌─────────────────────────────────────────────────────────────┐
│            SQLITE DATABASE (shakshuka.db)                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │ Tables:                                              │   │
│  │ • users (authentication)                             │   │
│  │ • tasks (task storage with strike tracking)         │   │
│  │ • settings (user preferences)                        │   │
│  │ • sessions (active sessions)                         │   │
│  │                                                      │   │
│  │ Indexes:                                             │   │
│  │ • idx_tasks_user_id (fast lookups)                  │   │
│  │ • idx_tasks_status (filter by status)               │   │
│  │ • idx_tasks_completed (completed retrieval)         │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

---

## 📚 COMPREHENSIVE METHODS REFERENCE

### 1️⃣ MAIN ENTRY POINT (main.py)

#### `setup_paths()`
```python
Purpose: Configure Python import paths for development vs. bundled execution
- Handles PyInstaller frozen executable mode
- Sets up sys.path for module discovery
- Returns: None (side effect: modifies sys.path)
```

#### `main()`
```python
Purpose: Orchestrate full application startup and initialization
Steps:
  1. setup_paths()
  2. initialize_data_manager()  → Database ready
  3. start_auto_save()          → Background thread starts
  4. start_scheduler()          → Daily jobs ready
  5. start_system_tray()        → Windows system tray icon
  6. open_browser()             → Auto-launch at http://127.0.0.1:8989
  7. Flask app.run()            → Server starts

Returns: None (never returns; app runs until shutdown)
Handles: ImportError, Exception (with graceful fallback)
```

---

### 2️⃣ CORE APP MODULE (src/app.py) - 119+ METHODS

#### **CLASS: AppContext**
Centralized application state manager with thread-safe properties.

| Method | Parameters | Returns | Purpose |
|--------|-----------|---------|---------|
| `__init__()` | None | None | Initialize all state properties, locks, and flags |
| `generate_session_secret(user_id)` | str | str | Create 32-byte secure random token for user |
| `validate_session_secret(user_id, secret)` | str, str | bool | Check if session token matches stored value |
| `generate_csrf_token()` | None | str | Create CSRF token with 15-min expiration |
| `validate_csrf_token(token)` | str | bool | Verify CSRF token validity and expiration |
| `cleanup_expired_tokens()` | None | None | Remove expired CSRF tokens from memory |
| `is_auto_save_running()` | None | bool | Check if auto-save thread is active |
| `set_auto_save_running(running)` | bool | None | Control auto-save thread state |
| `is_save_in_progress()` | None | bool | Check if database save operation ongoing |
| `set_save_in_progress(in_progress)` | bool | None | Flag when save starts/ends |
| `get_last_save_time()` | None | float | Retrieve timestamp of last save |
| `set_last_save_time(save_time)` | float | None | Update last save timestamp |
| `stop_auto_save_event()` | None | None | Signal auto-save thread to stop |
| `wait_for_auto_save_stop(timeout)` | int | bool | Wait for auto-save graceful shutdown |
| `clear_auto_save_stop_event()` | None | None | Reset stop event for restart |

#### **AUTHENTICATION & SESSION ROUTES**

##### `@app.route('/api/auth/login', methods=['POST'])`
```python
Function: api_auth_login()
Input JSON:
  {
    "password": "user_password",
    "username": "optional_username"
  }
Process:
  1. Rate limit check (100 req/5 min)
  2. Input sanitization
  3. Password verification (bcrypt)
  4. Session creation (24-hour expiry)
  5. CSRF token generation
  6. Return auth cookie

Response: 
  {
    "success": true,
    "username": "admin",
    "session_secret": "token...",
    "csrf_token": "csrf..."
  }
HTTP Status: 200 (success), 401 (invalid), 429 (rate limit)
```

##### `@app.route('/api/auth/logout', methods=['POST'])`
```python
Function: api_logout()
Input: None (uses session cookie)
Process:
  1. Retrieve session ID from cookie
  2. Invalidate session in database
  3. Clear session secret cache
  4. Delete auth cookie

Response:
  { "success": true }
HTTP Status: 200
```

##### `@app.route('/api/auth/status', methods=['GET'])`
```python
Function: api_auth_status()
Input: None (checks session cookie)
Process:
  1. Verify session validity
  2. Check password set status
  3. Retrieve settings

Response:
  {
    "authenticated": true,
    "password_set": true,
    "settings": { /* user settings */ }
  }
HTTP Status: 200
```

##### `@app.route('/verify-session', methods=['POST'])`
```python
Function: verify_session()
Input JSON:
  {
    "session_secret": "token...",
    "csrf_token": "csrf..."
  }
Process:
  1. Validate session secret
  2. Validate CSRF token
  3. Check session expiry

Response:
  { "valid": true/false }
HTTP Status: 200
```

#### **TASK MANAGEMENT ROUTES**

##### `@app.route('/api/tasks', methods=['GET'])`
```python
Function: get_tasks()
Query Parameters:
  - status: pending|completed|all
  - priority: high|medium|low|all
  - sort_by: created_at|due_date|priority
Process:
  1. @require_auth check
  2. @rate_limit check
  3. Get user ID from session
  4. Query database with filters
  5. Apply sorting
  6. Return task list

Response:
  {
    "tasks": [
      {
        "id": "uuid",
        "title": "Task name",
        "priority": "high",
        "status": "pending",
        "completed": false,
        ...
      }
    ],
    "count": 25
  }
HTTP Status: 200, 401 (auth), 429 (rate limit)
```

##### `@app.route('/api/tasks', methods=['POST'])`
```python
Function: create_task()
Input JSON:
  {
    "title": "New Task",
    "description": "Task details",
    "project": "Work",
    "priority": "high|medium|low",
    "due_date": "2025-10-25T14:30:00",
    "estimated_duration": 60
  }
Process:
  1. @require_auth check
  2. @require_csrf check
  3. @rate_limit check
  4. Validate task data schema
  5. Sanitize all input fields
  6. Generate UUID for task
  7. Insert into database
  8. Return created task

Response:
  {
    "success": true,
    "task": { /* full task object */ },
    "id": "new-task-uuid"
  }
HTTP Status: 201, 400 (validation error), 401, 403 (CSRF)
```

##### `@app.route('/api/tasks/<task_id>', methods=['PUT'])`
```python
Function: update_task(task_id)
Input JSON:
  {
    "title": "Updated title",  // Optional
    "description": "...",      // Optional
    "priority": "low",         // Optional
    "status": "in_progress",   // Optional
    "due_date": "...",         // Optional
    ...
  }
Process:
  1. @require_auth check
  2. @require_csrf check
  3. Verify task ownership
  4. Validate input schema
  5. Update database
  6. Return updated task

Response:
  {
    "success": true,
    "task": { /* updated task */ }
  }
HTTP Status: 200, 404 (task not found), 403 (unauthorized)
```

##### `@app.route('/api/tasks/<task_id>', methods=['DELETE'])`
```python
Function: delete_task(task_id)
Input: URL parameter (task_id)
Process:
  1. @require_auth check
  2. @require_csrf check
  3. Verify task ownership
  4. Delete from database
  5. Log deletion

Response:
  { "success": true }
HTTP Status: 200, 404 (not found), 403 (unauthorized)
```

##### `@app.route('/api/tasks/<task_id>/complete', methods=['POST'])`
```python
Function: complete_task(task_id)
Input: URL parameter (task_id)
Process:
  1. @require_auth check
  2. Mark completed = true
  3. Set completed_at = current_timestamp
  4. Update statistics
  5. Trigger auto-save

Response:
  {
    "success": true,
    "task": { /* task with updated status */ }
  }
HTTP Status: 200
```

##### `@app.route('/api/tasks/<task_id>/strike', methods=['POST'])`
```python
Function: strike_task(task_id)
Input JSON:
  {
    "strike_report": "Couldn't complete due to...",
    "defer": true  // Optional: move to next day
  }
Process:
  1. Mark struck_today = true
  2. Increment strike_count
  3. Set struck_date = current_timestamp
  4. Store strike reason
  5. Unschedule if scheduled

Response:
  {
    "success": true,
    "task": { /* updated task */ }
  }
HTTP Status: 200
```

##### `@app.route('/api/tasks/<task_id>/undo-strike', methods=['POST'])`
```python
Function: undo_strike(task_id)
Input: URL parameter (task_id)
Process:
  1. Set struck_today = false
  2. Clear struck_date
  3. Decrement strike_count (≥0)
  4. Clear strike_report

Response:
  {
    "success": true,
    "task": { /* updated task */ }
  }
HTTP Status: 200
```

##### `@app.route('/api/tasks/<task_id>/schedule', methods=['POST'])`
```python
Function: schedule_task(task_id)
Input JSON:
  {
    "scheduled_hour": 14,        // 0-23
    "scheduled_duration": 120,   // minutes
    "scheduled_date": "2025-10-25"  // Optional
  }
Process:
  1. Validate hour range (0-23)
  2. Validate duration > 0
  3. Unschedule any existing schedule
  4. Set new schedule
  5. Update database

Response:
  {
    "success": true,
    "task": { /* updated task */ }
  }
HTTP Status: 200
```

##### `@app.route('/api/tasks/<task_id>/unschedule', methods=['POST'])`
```python
Function: unschedule_task(task_id)
Input: URL parameter
Process:
  1. Clear scheduled_hour
  2. Clear scheduled_duration
  3. Update database

Response:
  { "success": true }
HTTP Status: 200
```

#### **SETTINGS ROUTES**

##### `@app.route('/api/settings', methods=['GET'])`
```python
Function: get_settings()
Process:
  1. @require_auth check
  2. Get user ID
  3. Query settings from database
  4. Return all settings

Response:
  {
    "theme": "orange",
    "dpi_scale": 100,
    "autosave_interval": 30,
    "notifications": true,
    "autostart_enabled": false,
    "daily_reset_time": "06:00",
    "work_hours_start": 9,
    "work_hours_end": 17,
    ...
  }
HTTP Status: 200
```

##### `@app.route('/api/settings', methods=['POST'])`
```python
Function: update_settings()
Input JSON:
  {
    "theme": "dark|light|auto|orange",
    "autosave_interval": 30,
    "notifications": true,
    ...
  }
Process:
  1. @require_auth check
  2. @require_csrf check
  3. Validate setting values
  4. Update database
  5. Apply settings to app context
  6. Return updated settings

Response:
  { "success": true, "settings": { /* updated */ } }
HTTP Status: 200
```

#### **SCHEDULE & PLANNER ROUTES**

##### `@app.route('/api/schedule', methods=['GET'])`
```python
Function: get_schedule()
Query Parameters:
  - date: "2025-10-25" (optional, defaults to today)
Process:
  1. @require_auth check
  2. Get tasks scheduled for date
  3. Organize by hour (0-23)
  4. Calculate time conflicts
  5. Return schedule structure

Response:
  {
    "date": "2025-10-25",
    "daily_reset_time": "06:00",
    "timezone": "UTC",
    "scheduled_tasks": {
      "6": [{ /* task 1 */ }, { /* task 2 */ }],
      "14": [{ /* task 3 */ }],
      ...
    },
    "unscheduled_tasks": [{ /* not scheduled */ }]
  }
HTTP Status: 200
```

##### `@app.route('/api/schedule', methods=['POST'])`
```python
Function: update_schedule()
Input JSON:
  {
    "daily_reset_time": "06:00",
    "timezone": "UTC",
    "scheduled_tasks": { /* task IDs by hour */ }
  }
Process:
  1. @require_auth check
  2. @require_csrf check
  3. Validate reset time format
  4. Update all scheduled tasks
  5. Save to database

Response:
  { "success": true }
HTTP Status: 200
```

#### **DATA IMPORT/EXPORT ROUTES**

##### `@app.route('/api/tasks/import', methods=['POST'])`
```python
Function: import_tasks()
Input: Multipart form data
  - file: CSV/TXT/JSON file
  - format: "csv|txt|json"
Process:
  1. @require_auth check
  2. @require_csrf check
  3. Read file content
  4. Parse based on format
  5. Validate each task
  6. Insert into database
  7. Return import results

Response:
  {
    "success": true,
    "imported": 15,
    "errors": 2,
    "error_details": [...]
  }
HTTP Status: 200, 400 (invalid format)
```

##### `@app.route('/api/export/csv', methods=['GET'])`
```python
Function: export_tasks_csv()
Query Parameters:
  - filter: pending|completed|all
  - date_from: ISO8601 date
  - date_to: ISO8601 date
Process:
  1. @require_auth check
  2. Query filtered tasks
  3. Format as CSV
  4. Return as download

Response: CSV file (Content-Type: text/csv)
HTTP Status: 200
```

#### **SYSTEM & MONITORING ROUTES**

##### `@app.route('/api/health', methods=['GET'])`
```python
Function: health_check()
Process:
  1. Check database connectivity
  2. Check auto-save thread status
  3. Check scheduler status
  4. Return health status

Response:
  {
    "status": "healthy|degraded|offline",
    "database": true,
    "auto_save": true,
    "scheduler": true,
    "uptime_seconds": 3600,
    "memory_mb": 125.3
  }
HTTP Status: 200
```

##### `@app.route('/api/health/detailed', methods=['GET'])`
```python
Function: detailed_health_check()
Extended health information:
  - Version info
  - Database statistics (table counts)
  - Active sessions count
  - Memory usage details
  - CPU usage percentage
  - Disk usage percentage
  - Recent errors (if any)
  - Build information

Response: Detailed diagnostics JSON
HTTP Status: 200
```

##### `@app.route('/api/metrics', methods=['GET'])`
```python
Function: get_metrics()
Process:
  1. Retrieve monitoring data
  2. Calculate statistics
  3. Format performance metrics

Response:
  {
    "cpu_usage": { "current": 15.2, "avg": 12.5, "peak": 45.3 },
    "memory_usage": { "current": 125.3, "available": 7847.2 },
    "disk_usage": 45.2,
    "request_count": 12540,
    "response_times": { "avg": 0.145, "p95": 0.523, "p99": 1.234 },
    "error_rate": 0.12,
    "active_sessions": 1,
    "task_count": 245
  }
HTTP Status: 200
```

##### `@app.route('/api/updates/check', methods=['GET'])`
```python
Function: check_updates()
Process:
  1. Query GitHub/update server
  2. Compare versions (current: 1.4.17)
  3. Return available versions

Response:
  {
    "current_version": "1.4.17",
    "latest_version": "1.4.18",
    "update_available": true,
    "changelog": "...",
    "download_url": "..."
  }
HTTP Status: 200
```

##### `@app.route('/shutdown', methods=['POST'])`
```python
Function: shutdown_server()
Process:
  1. @require_auth check
  2. Create final backup
  3. Save all data
  4. Stop auto-save thread
  5. Stop scheduler
  6. Shutdown Flask server
  7. Exit application (delayed)

Response:
  { "success": true, "message": "Shutdown initiated" }
HTTP Status: 200 (but connection closes)
```

#### **DECORATOR FUNCTIONS**

##### `@require_auth`
```python
Decorator for routes requiring authentication

Protected Method Flow:
  1. Check for session cookie
  2. Validate session_secret
  3. Verify session not expired
  4. Extract user_id
  5. Proceed to route
  OR
  6. Return 401 Unauthorized

Usage:
  @app.route('/api/protected')
  @require_auth
  def protected_route():
      user_id = get_user_id()
      ...
```

##### `@require_csrf`
```python
Decorator for CSRF protection on state-changing operations (POST, PUT, DELETE)

Flow:
  1. Get CSRF token from X-CSRF-Token header
  2. Validate token exists
  3. Validate token matches user session
  4. Validate token not expired (15 min)
  5. Proceed to route
  OR
  6. Return 403 Forbidden

Usage:
  @app.route('/api/tasks', methods=['POST'])
  @require_csrf
  def create_task():
      ...
```

##### `@rate_limit`
```python
Decorator for rate limiting by IP address

Flow:
  1. Extract client IP from request
  2. Call security_manager.check_rate_limit(ip)
  3. If under limit: proceed to route
  4. If exceeded: return 429 Too Many Requests

Config:
  - Max: 100 requests per IP
  - Window: 5 minutes
  - Auto-cleanup: Every 10 minutes

Usage:
  @app.route('/api/login', methods=['POST'])
  @rate_limit
  def login():
      ...
```

#### **BACKGROUND WORKER THREADS**

##### `auto_save_worker()`
```python
Background thread for automatic task persistence

Configuration:
  - Default interval: 30 seconds
  - Configurable range: 15 seconds to 5 minutes
  - Check: Only saves if changes detected

Process Loop:
  while app_context.auto_save_enabled:
    sleep(configured_interval)
    if changes_detected():
      save_all_tasks_to_database()
      update_statistics()
      trigger_monitoring()
    
Graceful Shutdown:
  - Monitors stop_event
  - Saves pending changes
  - Closes connections cleanly
  - Logs shutdown

Error Handling:
  - Catches database errors
  - Logs to application logger
  - Retries on transient failures
  - Alert on critical failures
```

##### `scheduler_worker()`
```python
Background thread for scheduled jobs and daily events

Jobs:
  1. Daily reset (strike counters, statistics)
  2. Session cleanup (remove expired sessions)
  3. Token cleanup (remove expired CSRF tokens)
  4. Backup operations (periodic backups)
  5. Update checks (if auto-check enabled)

Scheduling:
  - Uses schedule library
  - Configurable reset time (default: 6:00 AM)
  - Respects user's timezone preference

Error Handling:
  - Catches job exceptions
  - Logs errors with context
  - Continues with other jobs
  - Implements exponential backoff on repeated failures
```

#### **UTILITY FUNCTIONS**

##### `sanitize_input(data: str | dict, max_length: int = 1000) -> str | dict`
```python
XSS Prevention Function

Process:
  1. Convert to string if needed
  2. Limit length to max_length
  3. HTML escape all characters
  4. Remove script tags
  5. Remove javascript: protocols
  6. Remove dangerous characters (<, >, ", ')
  7. Strip whitespace

Returns: Sanitized string or dict with sanitized values
Example:
  Input:  "<script>alert('xss')</script>Hello"
  Output: "Hello"
```

##### `validate_task_data(task_data: dict) -> tuple[bool, Optional[str]]`
```python
Task Schema Validation

Checks:
  - title: required, 1-500 chars
  - description: optional, 0-5000 chars
  - project: optional, valid category
  - priority: one of [high, medium, low]
  - status: one of [pending, in_progress, completed]
  - due_date: optional, valid ISO8601 datetime
  - estimated_duration: optional, positive integer (minutes)
  - scheduled_hour: optional, 0-23 range
  - scheduled_duration: optional, positive integer

Returns: (is_valid: bool, error_message: Optional[str])
Example:
  valid, msg = validate_task_data({"title": "", "priority": "invalid"})
  # Returns: (False, "Title required and priority must be high|medium|low")
```

##### `ensure_data_manager() -> bool`
```python
Initialize SQLiteDataManager if not already created

Process:
  1. Check if data_manager already initialized
  2. If not: create SQLiteDataManager instance
  3. Store in AppContext
  4. Run database migrations
  5. Verify tables created

Returns: True if successful, False if error
Side Effects: Modifies app_context.data_manager
```

##### `initialize_data_manager() -> bool`
```python
Full data manager initialization with error handling

Process:
  1. ensure_data_manager()
  2. Verify database integrity
  3. Run migrations
  4. Create default user if needed
  5. Load encryption keys
  6. Initialize backup system
  7. Initialize monitoring

Returns: True if successful, False if initialization fails
```

---

### 3️⃣ DATABASE MODULE (src/sqlite_data_manager.py)

#### **CLASS: SQLiteDataManager**
Thread-safe SQLite wrapper for persistent data storage.

| Method | Parameters | Returns | Thread-Safe |
|--------|-----------|---------|------------|
| `_init_database()` | None | None | ✓ |
| `_run_migrations()` | None | None | ✓ |
| `_get_connection()` | None | sqlite3.Connection | ✓ |
| `create_user(username, password)` | str, str | Dict[str, Any] | ✓ |
| `verify_user(username, password)` | str, str | Optional[Dict] | ✓ |
| `add_task(user_id, task_data)` | str, Dict | str (task_id) | ✓ |
| `get_tasks(user_id, filters)` | str, Dict | List[Dict] | ✓ |
| `get_task(task_id)` | str | Optional[Dict] | ✓ |
| `update_task(task_id, updates)` | str, Dict | bool | ✓ |
| `delete_task(task_id)` | str | bool | ✓ |
| `get_user_settings(user_id)` | str | Dict | ✓ |
| `update_user_settings(user_id, settings)` | str, Dict | bool | ✓ |
| `backup_database()` | None | str (backup_path) | ✓ |
| `restore_backup(backup_path)` | str | bool | ✓ |
| `get_backup_list()` | None | List[str] | ✓ |
| `delete_old_backups(days)` | int | int (deleted_count) | ✓ |
| `get_database_stats()` | None | Dict[str, int] | ✓ |

#### Key Database Methods

##### `add_task(user_id: str, task_data: Dict) -> str`
```python
Insert new task into database

Parameters:
  user_id: UUID of task owner
  task_data: {
    "title": str,
    "description": str,
    "project": str,
    "priority": "high|medium|low",
    "due_date": ISO8601 datetime,
    "estimated_duration": int (minutes),
    ...
  }

Process:
  1. Acquire lock
  2. Generate UUID for task
  3. Set timestamps (created_at, updated_at = now)
  4. Insert into tasks table
  5. Create indexes
  6. Commit transaction
  7. Release lock

Returns: task_id (UUID string)
Raises: sqlite3.IntegrityError (duplicate), sqlite3.OperationalError (DB error)
```

##### `get_tasks(user_id: str, filters: Dict = {}) -> List[Dict]`
```python
Retrieve tasks with optional filtering

Parameters:
  user_id: UUID of task owner
  filters: {
    "status": "pending|completed|all",
    "priority": "high|medium|low|all",
    "project": str (specific project),
    "sort_by": "created_at|due_date|priority",
    "sort_order": "ASC|DESC",
    "limit": int,
    "offset": int
  }

Returns: List of task dictionaries
- Empty list if no tasks match filters
- Tasks sorted by specified criteria
```

##### `update_task(task_id: str, updates: Dict) -> bool`
```python
Modify existing task

Parameters:
  task_id: UUID of task
  updates: Dict with fields to update
    {
      "title": "New title",
      "status": "in_progress",
      "completed": true,
      "completed_at": ISO8601,
      "struck_today": true,
      "strike_count": 2,
      ...
    }

Process:
  1. Verify task exists
  2. Check task ownership
  3. Apply updates
  4. Set updated_at = now
  5. Commit changes

Returns: bool (True if success, False if task not found)
```

##### `backup_database() -> str`
```python
Create full database backup

Process:
  1. Generate timestamp-based backup name
  2. Create backups/ directory if needed
  3. Copy database file to backup location
  4. Create metadata (timestamp, version info)
  5. Store in: data/backups/{timestamp}/
  6. Delete backups older than 30 days

Returns: Backup directory path
Backup Contents:
  - shakshuka.db (database copy)
  - metadata.json (backup info, version, timestamp)
  - manifest.txt (file listing)
```

##### `restore_backup(backup_path: str) -> bool`
```python
Restore database from backup

Parameters:
  backup_path: Full path to backup directory

Process:
  1. Verify backup exists and is valid
  2. Create current database backup (safety)
  3. Close active connections
  4. Restore database file from backup
  5. Run integrity check
  6. Reconnect and verify
  7. Rollback on failure (restore safety backup)

Returns: bool (True if success, False if restore failed)
```

---

### 4️⃣ SECURITY MODULE (src/security_manager.py)

#### **CLASS: SecurityManager**
Centralized security management for rate limiting, input sanitization, session security.

| Method | Parameters | Returns | Purpose |
|--------|-----------|---------|---------|
| `sanitize_input(text, max_length)` | str, int | str | XSS prevention |
| `check_rate_limit(client_ip)` | str | bool | IP-based throttling |
| `get_rate_limit_stats()` | None | Dict | Usage statistics |
| `clear_rate_limit_for_ip(client_ip)` | str | None | Reset IP quota |
| `get_blocked_ips()` | None | List[str] | Currently blocked IPs |

#### Key Security Methods

##### `check_rate_limit(client_ip: str) -> bool`
```python
Rate Limit Checker with Auto-Cleanup

Configuration:
  - Window: 5 minutes (300 seconds)
  - Max Requests: 100 per window per IP
  - Cleanup Interval: 10 minutes
  - Max IPs Tracked: 1,000

Algorithm:
  1. Lock acquired for thread safety
  2. Check if cleanup needed (last_cleanup > 10 min ago)
  3. If cleanup needed: remove expired IPs
  4. Get or create request deque for IP
  5. Remove requests older than 5 minutes
  6. If deque length >= 100: return False (blocked)
  7. Add current request timestamp
  8. Return True (allowed)

Returns: bool
  - True: Request allowed
  - False: Request blocked (rate limit exceeded)

Blocked Response:
  HTTP 429 Too Many Requests
  Retry-After: 300 seconds

Example:
  For IP 192.168.1.100:
    Request 1-100: allowed
    Request 101: blocked (429)
    After 5 minutes: queue resets, requests allowed again
```

##### `sanitize_input(text: str, max_length: int = 1000) -> str`
```python
XSS Prevention Through Input Sanitization

Process:
  1. Check if text is empty → return ""
  2. Truncate to max_length (default 1000)
  3. HTML escape: converts <, >, &, ", ' to entities
  4. Regex remove: <script>...</script> tags
  5. Regex remove: javascript: protocols
  6. Regex remove: dangerous chars like <, >, ", '
  7. Strip leading/trailing whitespace
  8. Return sanitized text

Attacks Prevented:
  - <script>alert('xss')</script> → ""
  - <img src=x onerror=alert(1)> → "&lt;img src=x onerror=alert(1)&gt;"
  - javascript:alert(1) → "alert(1)"
  - Attribute-based XSS
  - Event handler injections

Returns: str (sanitized input)
Example:
  Input:  "<b onclick='alert(1)'>Click me</b>"
  Output: "&lt;b onclick='alert(1)'&gt;Click me&lt;/b&gt;"
```

---

### 5️⃣ USER AUTHENTICATION (src/user_manager.py)

#### **CLASS: UserManager**
User registration, authentication, session management.

| Method | Parameters | Returns | Purpose |
|--------|-----------|---------|---------|
| `create_user(username, password)` | str, str | Dict | User registration |
| `verify_user(username, password)` | str, str | Optional[Dict] | User login |
| `change_password(user_id, old_pwd, new_pwd)` | str, str, str | bool | Password update |
| `create_session(user_id)` | str | str | Session creation |
| `verify_session(session_id)` | str | Optional[Dict] | Session validation |
| `invalidate_session(session_id)` | str | bool | Logout |
| `cleanup_expired_sessions()` | None | int | Remove stale sessions |

#### Key Auth Methods

##### `create_user(username: str, password: str) -> Dict`
```python
User Registration

Parameters:
  username: Unique username (1-50 chars, alphanumeric + underscore)
  password: User password (min 8 chars, bcrypt hashed)

Process:
  1. Validate username format
  2. Check username not already taken
  3. Validate password strength (8+ chars)
  4. Hash password with bcrypt (12-round salt)
  5. Generate user UUID
  6. Insert user record
  7. Create default settings
  8. Create session
  9. Return user object with session token

Returns: {
    "id": "user-uuid",
    "username": "username",
    "created_at": "ISO8601",
    "session_id": "session-token",
    "session_expires_at": "ISO8601+24h"
  }
  
Raises: ValueError (invalid input), sqlite3.IntegrityError (duplicate username)
```

##### `verify_user(username: str, password: str) -> Optional[Dict]`
```python
User Authentication (Login)

Parameters:
  username: User's username
  password: User's password (plaintext)

Process:
  1. Query user from database by username
  2. If not found: return None
  3. Hash provided password
  4. Compare with stored hash using bcrypt
  5. If mismatch: return None
  6. If match: Create new session
  7. Invalidate old sessions (single session per user)
  8. Return user object with new session

Returns: User object with session OR None if authentication fails
  {
    "id": "user-uuid",
    "username": "username",
    "session_id": "new-session-token",
    "created_at": "ISO8601"
  }
```

##### `create_session(user_id: str) -> str`
```python
Session Creation

Parameters:
  user_id: UUID of user

Process:
  1. Generate secure random session ID (32 bytes)
  2. Calculate expiry: now + 24 hours
  3. Insert into sessions table
  4. Store session metadata in app context
  5. Return session ID

Returns: Session ID (32-byte secure random string)

Session Format:
  {
    "session_id": "random-32-byte-hex",
    "user_id": "user-uuid",
    "created_at": "ISO8601",
    "expires_at": "ISO8601+24h"
  }
```

##### `verify_session(session_id: str) -> Optional[Dict]`
```python
Session Validation

Parameters:
  session_id: Session token to verify

Process:
  1. Query session from database
  2. If not found: return None
  3. Check expiry: now < expires_at
  4. If expired: return None
  5. Update last_activity timestamp
  6. Return session object

Returns: Session dict OR None if invalid/expired
```

---

### 6️⃣ MONITORING MODULE (src/monitoring.py)

#### **CLASS: PerformanceMonitor**
System and application performance metrics collection.

| Method | Parameters | Returns | Purpose |
|--------|-----------|---------|---------|
| `record_metric(name, value)` | str, float | None | Log metric |
| `record_timing(operation, duration)` | str, float | None | Track operation |
| `get_metrics()` | None | Dict | All metrics |
| `get_health_status()` | None | Dict | System health |
| `create_alert(alert_type, message, severity)` | str, str, str | None | Generate alert |
| `get_alerts()` | None | List[Dict] | Active alerts |

#### Metrics Collection

##### `record_metric(name: str, value: float) -> None`
```python
Log Performance Metric

Parameters:
  name: Metric name (e.g., "cpu_usage", "response_time")
  value: Numeric value

Storage:
  - Circular buffer (deque) per metric
  - Keeps last 1,000 entries
  - Timestamps added automatically
  - Thread-safe with RLock

Metrics Tracked:
  - cpu_usage: System CPU %
  - memory_usage: System memory %
  - memory_available: Available RAM GB
  - disk_usage: Disk usage %
  - process_cpu: Shakshuka CPU %
  - process_memory: Shakshuka memory MB
  - response_time: API response time (ms)
  - request_count: Total requests
  - error_count: Total errors
  - active_sessions: Current sessions
```

##### `get_health_status() -> Dict`
```python
Overall System Health Assessment

Returns: {
  "status": "healthy|degraded|critical",
  "overall_score": 95.2,  // 0-100
  "cpu": {
    "current": 15.2,
    "threshold": 80.0,
    "status": "healthy"
  },
  "memory": {
    "current": 45.3,
    "threshold": 80.0,
    "status": "healthy"
  },
  "disk": {
    "current": 67.8,
    "threshold": 90.0,
    "status": "healthy"
  },
  "alerts": 0,
  "error_rate": 0.05,  // percentage
  "response_time_avg": 0.145,  // seconds
  "uptime_seconds": 3600,
  "active_sessions": 1,
  "task_count": 245,
  "database_size_mb": 12.5
}
```

---

### 7️⃣ UPDATE MANAGER (src/update_manager.py)

#### **CLASS: UpdateManager**
OTA update handling with data preservation and rollback.

| Method | Parameters | Returns | Purpose |
|--------|-----------|---------|---------|
| `check_for_updates()` | None | Dict | Check available |
| `download_update(version)` | str | str (path) | Download |
| `install_update(package_path)` | str | bool | Install |
| `get_update_status()` | None | Dict | Current state |
| `compare_versions(v1, v2)` | str, str | int | Version compare |

#### Update Flow

##### `check_for_updates() -> Dict`
```python
Query for Available Updates

Process:
  1. Load current version: 1.4.17
  2. Query update server (GitHub releases API)
  3. Parse available versions
  4. Compare using semantic versioning
  5. Filter by update channel (stable/beta)
  6. Return available updates

Returns: {
  "current_version": "1.4.17",
  "latest_version": "1.4.18",
  "update_available": true,
  "versions": [
    {
      "version": "1.4.18",
      "release_date": "2025-10-25",
      "changelog": "...",
      "download_url": "...",
      "file_size": 45000000,
      "checksum": "sha256:..."
    }
  ],
  "channel": "stable"
}
```

##### `install_update(package_path: str) -> bool`
```python
Apply Update Safely

Parameters:
  package_path: Path to downloaded update package

Process:
  1. Create safety backup of current state
  2. Extract update package
  3. Verify file integrity (checksum)
  4. Backup user data
  5. Replace application files
  6. Update version.json
  7. Verify new version starts
  8. Cleanup old backups
  9. Log update completion

Returns: True if success, False if installation failed
Rollback: On failure, restores from backup and original state
```

---

## 📊 DATABASE SCHEMA

### Users Table
```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

**Purpose:** User account storage with credentials

### Tasks Table
```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    project TEXT,
    priority TEXT DEFAULT 'medium',
    status TEXT DEFAULT 'pending',
    completed BOOLEAN DEFAULT 0,
    completed_at TIMESTAMP,
    due_date TIMESTAMP,
    estimated_duration INTEGER DEFAULT 60,
    scheduled_hour INTEGER,
    scheduled_duration INTEGER,
    struck_today BOOLEAN DEFAULT 0,
    struck_date TIMESTAMP,
    strike_report TEXT,
    strike_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
)
```

**Purpose:** Task storage with scheduling and strike tracking

### Settings Table
```sql
CREATE TABLE settings (
    user_id TEXT PRIMARY KEY,
    theme TEXT DEFAULT 'orange',
    dpi_scale INTEGER DEFAULT 100,
    autosave_interval INTEGER DEFAULT 30,
    notifications BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
)
```

**Purpose:** User preferences and configuration

### Sessions Table
```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
)
```

**Purpose:** Active session tracking

---

## 🔐 SECURITY SPECIFICATIONS

### Rate Limiting
- **Algorithm:** Token bucket with 5-minute window
- **Limits:** 100 requests per 5 minutes per IP
- **Blocking:** Automatic 429 response
- **Cleanup:** Every 10 minutes (expired IPs)

### Session Management
- **Format:** Secure random 32-byte token
- **Lifetime:** 24 hours from creation
- **Storage:** sqlite3 sessions table + app context cache
- **Cleanup:** Every 12 hours (background job)
- **Single Session:** One active session per user (new login invalidates old)

### Password Security
- **Hashing:** bcrypt with 12-round salt (primary)
- **Fallback:** SHA256 if bcrypt unavailable
- **Upgrade:** Automatic on login if using fallback
- **Minimum:** 8 characters

### CSRF Protection
- **Token Format:** 32-byte secure random
- **Lifetime:** 15 minutes from generation
- **Validation:** On all state-changing operations (POST, PUT, DELETE)
- **Cleanup:** Every 15 minutes (expired tokens)

### Input Sanitization
- **Method:** HTML escaping + regex filtering
- **Coverage:** All user input (title, description, etc.)
- **Max Length:** 1000 characters (configurable)
- **Attacks Prevented:** XSS, script injection, event handlers

---

## 📈 PERFORMANCE CHARACTERISTICS

### Auto-Save
- **Interval:** 30 seconds (configurable 15s-5m)
- **Trigger:** Any task modification detected
- **Thread:** Daemon background thread
- **Graceful Shutdown:** Saves pending changes before exit

### Database Optimization
- **Mode:** WAL (Write-Ahead Logging) for concurrent access
- **Indexes:** 5 indexes on frequently queried fields
- **Connection Pool:** Thread-safe singleton manager
- **Locking:** RLock (reentrant) for thread safety

### Memory Management
- **Metric Storage:** Circular buffer (1000 entries per metric)
- **Rate Limit Cleanup:** Every 10 minutes
- **Token Cleanup:** Every 15 minutes
- **Session Cleanup:** Every 12 hours
- **Max IPs Tracked:** 1,000

### System Monitoring
- **Collection Interval:** 30 seconds
- **Metrics:** 6+ performance indicators
- **Alerts:** Automatic on threshold breach
- **Thresholds:** CPU 80%, Memory 80%, Disk 90%

---

## 🚀 DEPLOYMENT

### Build Process
```bash
python scripts/build.py
```

**Output:** 
- `Shakshuka.exe` (standalone executable)
- `Shakshuka-Setup-v1.4.17.exe` (installer)

### Installation Methods
1. **Portable:** Run `Shakshuka.exe` directly
2. **Installer:** Run `Shakshuka-Setup-v1.4.17.exe`
3. **From Source:** `python main.py`

### System Requirements
- **OS:** Windows 10/11 (primary)
- **Python:** 3.8+ (for source)
- **RAM:** 512 MB minimum
- **Storage:** 50 MB + data
- **Port:** 8989 (configurable)

---

## 📝 CONCLUSION

This comprehensive methods reference documents all major functions, classes, and API endpoints in the Shakshuka application. With 119+ core functions, 40+ API routes, and multiple background workers, the application provides a robust, secure, and user-friendly task management experience.

**Key Strengths:**
- ✅ Thread-safe architecture with RLocks
- ✅ Comprehensive security (rate limiting, CSRF, XSS prevention)
- ✅ Robust error handling and logging
- ✅ Automatic data persistence and backups
- ✅ Performance monitoring and alerts
- ✅ Beautiful, modern UI with responsive design

**Ready for Production:** Yes, with 1.4.17 build stable and tested.

---

**Last Updated:** October 22, 2025  
**Project Version:** 1.4.17  
**Documentation Version:** 1.0

