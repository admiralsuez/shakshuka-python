# SHAKSHUKA - Comprehensive Code Analysis & Methods Documentation

## Project Overview

**Shakshuka** is a modern, secure task management application built with Python Flask and featuring:
- Beautiful gradient UI with glass-morphism effects inspired by meditation apps
- Encrypted local data storage with SQLite
- Windows autostart integration
- Real-time auto-save functionality
- Drag-and-drop daily planner
- System tray integration
- Performance monitoring and metrics tracking

**Version:** 1.4.17 | **Build:** 31 | **Release:** 2025-10-22

---

## Architecture Overview

### Directory Structure
```
Shakshuka/
├── main.py                          # Entry point with path setup & initialization
├── src/
│   ├── app.py                      # Main Flask application (2800+ lines)
│   ├── security_manager.py         # Input sanitization, rate limiting
│   ├── sqlite_data_manager.py      # SQLite database management
│   ├── user_manager.py             # User authentication & session management
│   ├── update_manager.py           # OTA update handling
│   ├── monitoring.py               # Performance monitoring
│   └── app_core/
│       ├── settings.py             # App configuration
│       └── dirs.py                 # Directory management
├── assets/
│   ├── static/
│   │   ├── css/                    # Styling (style.css, tasks.css, etc.)
│   │   ├── js/                     # Frontend logic (app.js, auth.js, state.js, utils.js)
│   │   └── images/
│   └── templates/
│       └── index.html              # Single-page application template
├── config/
│   ├── requirements.txt            # Python dependencies
│   ├── version.json                # Version information
│   └── changelog.txt               # Release notes
├── data/                           # Encrypted data storage
├── tools/
│   ├── autostart.py                # Windows autostart utilities
│   ├── server-manager-gui.py       # GUI management tool
│   └── install.ps1, uninstall.ps1  # Installation scripts
├── scripts/
│   ├── build.py                    # Build executable script
│   ├── build-installer.bat         # Batch build script
│   ├── installer.iss               # InnoSetup installer config
│   └── Start-Shakshuka.bat         # Launch scripts
└── tests/
    ├── run_tests.py                # Test runner
    ├── test_unit.py                # Unit tests
    └── test_integration.py         # Integration tests
```

---

## Core Modules & Classes

### 1. **main.py** - Application Entry Point

**Purpose:** Bootstrap the application with proper path setup and initialization

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `setup_paths()` | Configure Python paths for development and bundled (PyInstaller) modes |
| `main()` | Main entry point that orchestrates initialization |

**Initialization Flow:**
```
setup_paths() 
  ↓
initialize_data_manager()
  ↓
start_auto_save() [30-second intervals]
  ↓
start_scheduler() [daily reset jobs]
  ↓
start_system_tray() [Windows integration]
  ↓
Flask server startup at http://127.0.0.1:8989
```

**Key Features:**
- Handles PyInstaller executable vs. development mode paths
- UTF-8 console encoding fix for Windows
- Auto-opens browser on startup
- Thread-safe initialization sequence
- Graceful error handling with fallback mechanisms

---

### 2. **src/app.py** - Flask Application Core

**Size:** ~2800 lines | **Components:** 119+ functions

#### A. Core Classes

##### **AppContext** - Global Application State Manager
Thread-safe centralized context replacing global variables.

```python
class AppContext:
    _data_manager          # SQLiteDataManager instance
    _autostart_manager     # Windows autostart handler
    _password_set          # Authentication flag
    _update_manager        # OTA update handler
    _auto_save_enabled     # Auto-save toggle
    _auto_save_thread      # Background thread reference
    
    # Session Management
    _session_secrets       # User session secret mapping
    _csrf_tokens          # CSRF token storage with expiration
    
    # Thread Safety
    _lock                 # RLock for atomic operations
    _auto_save_lock       # Dedicated auto-save lock
    
    # Auto-Save State
    _auto_save_running    # Running flag
    _auto_save_stop_event # Threading event for graceful shutdown
    _last_save_time       # Timestamp tracking
    _save_in_progress     # Save operation flag
```

**Methods:**
- `generate_session_secret(user_id)` - Create secure session token
- `validate_session_secret(user_id, secret)` - Verify session validity
- `generate_csrf_token()` - Create CSRF protection token
- `validate_csrf_token(token)` - Verify CSRF token (15-min expiration)
- `cleanup_expired_tokens()` - Memory management for expired tokens
- `is_auto_save_running()` - Check auto-save thread status
- `set_auto_save_running(running)` - Control auto-save state

#### B. Core Route Functions

##### **Authentication & Session Management**

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/auth/login` | POST | Authenticate user with password |
| `/api/auth/status` | GET | Check authentication status |
| `/api/auth/logout` | POST | Terminate user session |
| `/api/csrf-token` | GET | Request CSRF token for forms |
| `/verify-session` | POST | Validate session token |
| `/change-password` | POST | Update user password |

**Authentication Flow:**
```
User Login Request
  ↓
rate_limit() check [100 req/5 min]
  ↓
Password verification (bcrypt if available)
  ↓
Session creation with secret token
  ↓
CSRF token generation (15-min TTL)
  ↓
Response with auth cookie
```

##### **Task Management (CRUD Operations)**

| Route | Method | Purpose | Auth Required |
|-------|--------|---------|---|
| `/api/tasks` | GET | Retrieve all user tasks | ✓ |
| `/api/tasks` | POST | Create new task | ✓ |
| `/api/tasks/<id>` | PUT | Update task | ✓ |
| `/api/tasks/<id>` | DELETE | Delete task | ✓ |
| `/api/tasks/<id>/complete` | POST | Mark task complete | ✓ |
| `/api/tasks/<id>/strike` | POST | Mark task as struck | ✓ |
| `/api/tasks/<id>/undo-strike` | POST | Undo strike | ✓ |

**Task Schema:**
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "title": "Task name",
  "description": "Detailed description",
  "project": "category",
  "priority": "high|medium|low",
  "status": "pending|in_progress|completed",
  "completed": false,
  "completed_at": "ISO8601",
  "due_date": "ISO8601",
  "estimated_duration": 60,
  "scheduled_hour": 14,
  "scheduled_duration": 120,
  "struck_today": false,
  "struck_date": "ISO8601",
  "strike_report": "reason",
  "strike_count": 0,
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

##### **Scheduling & Planner**

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/schedule` | GET | Get daily schedule |
| `/api/schedule` | POST | Update schedule |
| `/api/tasks/<id>/schedule` | POST | Schedule task to time slot |
| `/api/tasks/<id>/unschedule` | POST | Remove from schedule |
| `/api/reset-daily-strikes` | POST | Reset daily strike counters |

**Schedule Structure:**
```json
{
  "daily_reset_time": "06:00",
  "timezone": "UTC",
  "scheduled_tasks": {
    "0": [],          // Midnight
    "6": ["task-id"], // 6 AM
    "14": ["task-id"] // 2 PM
  }
}
```

##### **Settings & Configuration**

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/settings` | GET | Retrieve user settings |
| `/api/settings` | POST | Update user settings |
| `/api/settings/export` | GET | Export settings as JSON |

**Settings Schema:**
```json
{
  "theme": "orange|light|dark|auto",
  "dpi_scale": 100,
  "autosave_interval": 30,
  "notifications": true,
  "autostart_enabled": false,
  "daily_reset_time": "06:00",
  "work_hours_start": 9,
  "work_hours_end": 17
}
```

##### **Data Import/Export**

| Route | Method | Purpose | Format |
|-------|--------|---------|--------|
| `/api/tasks/import` | POST | Import tasks | CSV/TXT/JSON |
| `/api/export/csv` | GET | Export as CSV | text/csv |
| `/api/export/metrics` | GET | Export metrics | JSON |

##### **Updates & System**

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/updates/check` | GET | Check for updates |
| `/api/updates/download` | POST | Download update |
| `/api/updates/install` | POST | Install update |
| `/api/health` | GET | Health status check |
| `/api/health/detailed` | GET | Detailed diagnostics |
| `/api/metrics` | GET | Performance metrics |
| `/api/monitoring/rate-limit-stats` | GET | Rate limit statistics |
| `/changelog` | GET | Release notes |
| `/shutdown` | POST | Graceful shutdown |

#### C. Middleware & Decorators

##### **rate_limit(f)**
Rate limiting decorator with IP-based throttling.
- **Config:** 100 requests per 5 minutes per IP
- **Response:** 429 Too Many Requests if exceeded

##### **require_auth(f)**
Authentication decorator checking session validity.
- **Check:** Session secret presence and validity
- **Response:** 401 Unauthorized if invalid

##### **require_csrf(f)**
CSRF protection decorator for state-changing operations.
- **Check:** CSRF token presence and validity (15-min expiration)
- **Response:** 403 Forbidden if invalid

##### **after_request(response)**
Response middleware for security headers:
```
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
X-XSS-Protection: 1; mode=block
Cache-Control: no-cache, no-store, must-revalidate
```

#### D. Background Threads

##### **auto_save_worker()**
Automatic task persistence thread.

**Function:**
```python
def auto_save_worker():
    """Background auto-save worker (30s default interval)"""
    while app_context.auto_save_enabled:
        time.sleep(app_context.get_last_save_time())
        if changes_detected():
            save_all_tasks()
            update_statistics()
```

**Configuration:**
- **Interval:** 30 seconds (configurable 15s-5m)
- **Trigger:** Any task modification
- **Fallback:** Manual save via UI

##### **scheduler_worker()**
Daily reset and scheduled event handler.

**Events:**
- Daily strike counter reset
- Scheduled task notifications
- Session cleanup
- Backup operations

#### E. Data Management Functions

**Database Functions:**

| Function | Purpose |
|----------|---------|
| `ensure_data_manager()` | Initialize SQLiteDataManager |
| `initialize_data_manager()` | Setup database with migrations |
| `get_user_id()` | Extract user from session |
| `sanitize_input(data)` | XSS prevention |
| `validate_task_data(task_data)` | Schema validation |

**Task Functions:**

| Function | Purpose |
|----------|---------|
| `get_tasks()` | Retrieve filtered tasks |
| `create_task()` | Insert new task with ID generation |
| `update_task(id)` | Modify task properties |
| `delete_task(id)` | Remove task from database |
| `complete_task(id)` | Mark completed with timestamp |
| `strike_task(id)` | Mark failed/struck task |
| `undo_strike(id)` | Revert strike status |
| `schedule_task(id)` | Assign to time slot |
| `unschedule_task(id)` | Remove from schedule |

**Backup Functions:**

| Function | Purpose |
|----------|---------|
| `create_backup()` | Full data snapshot |
| `restore_backup()` | Restore from backup |
| `validate_backup_integrity()` | Verify backup validity |
| `get_backups()` | List available backups |

---

### 3. **src/security_manager.py** - Security & Rate Limiting

**Purpose:** Handle encryption, input validation, rate limiting, and session security

#### Key Classes

##### **SecurityManager**

**Attributes:**
```python
rate_limit_requests      # deque per IP tracking
rate_limit_window        # 5-minute window
max_requests_per_window  # 100 req/window
session_secrets          # User session token storage
cleanup_interval         # 10-minute auto-cleanup
```

**Methods:**

| Method | Purpose | Returns |
|--------|---------|---------|
| `sanitize_input(text, max_length=1000)` | XSS prevention (HTML escape, script removal) | str |
| `check_rate_limit(client_ip)` | Rate limit check with auto-cleanup | bool |
| `get_rate_limit_stats()` | Usage statistics | dict |
| `clear_rate_limit_for_ip(client_ip)` | Reset IP quota | None |

**Rate Limit Algorithm:**
```
For each IP:
  1. Remove requests older than 5 minutes
  2. If count >= 100, return False (blocked)
  3. Add current request timestamp
  4. Return True (allowed)
```

**Memory Management:**
- Auto-cleanup every 10 minutes
- Tracks up to 1,000 unique IPs
- Deque per IP with max window

---

### 4. **src/sqlite_data_manager.py** - Database Management

**Purpose:** Thread-safe SQLite database operations with encryption-ready storage

#### SQLiteDataManager Class

**Database Schema:**

##### **users table**
```sql
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT UNIQUE,
    password_hash TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

##### **tasks table**
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

##### **settings table**
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

##### **sessions table**
```sql
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
)
```

**Indexes:**
- `idx_tasks_user_id` - Fast user task lookup
- `idx_tasks_status` - Filter by status
- `idx_tasks_completed` - Completed task retrieval
- `idx_sessions_user_id` - User session lookup
- `idx_sessions_expires` - Expired session cleanup

**Key Methods:**

| Method | Purpose | Thread-Safe |
|--------|---------|------------|
| `create_user(username, password)` | Register new user | ✓ |
| `verify_user(username, password)` | Authentication | ✓ |
| `add_task(user_id, task_data)` | Insert task | ✓ |
| `get_tasks(user_id, filters)` | Retrieve filtered tasks | ✓ |
| `update_task(task_id, updates)` | Modify task | ✓ |
| `delete_task(task_id)` | Remove task | ✓ |
| `get_user_settings(user_id)` | Retrieve settings | ✓ |
| `update_user_settings(user_id, settings)` | Save settings | ✓ |
| `backup_database()` | Full snapshot | ✓ |
| `restore_backup(backup_path)` | Restore from snapshot | ✓ |

**Thread Safety:**
- Uses RLock (reentrant lock) for nested locking
- Each method wrapped with lock context
- WAL (Write-Ahead Logging) mode for concurrent access
- Foreign key constraints enabled

---

### 5. **src/user_manager.py** - User Authentication

**Purpose:** User registration, authentication, and session management

#### UserManager Class

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `create_user(username, password)` | Register new user with bcrypt hashing |
| `verify_user(username, password)` | Check credentials |
| `change_password(user_id, old_pwd, new_pwd)` | Update password |
| `create_session(user_id)` | Generate session with 24-hour expiry |
| `verify_session(session_id)` | Check session validity |
| `invalidate_session(session_id)` | Logout user |
| `cleanup_expired_sessions()` | Remove stale sessions |

**Password Security:**
- Uses bcrypt with configurable salt rounds (default: 12)
- Fallback to SHA256 if bcrypt unavailable
- Automatic password upgrade on login

**Session Management:**
- Session ID: secure random token (32 bytes)
- Expiry: 24 hours from creation
- Auto-cleanup every 12 hours
- Single session per user (login creates new session)

---

### 6. **src/update_manager.py** - OTA Updates

**Purpose:** Handle over-the-air updates with data preservation

#### UpdateManager Class

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `check_for_updates()` | Query GitHub/update server |
| `download_update(version)` | Fetch update package |
| `install_update(package_path)` | Apply update safely |
| `create_backup()` | Full backup before update |
| `restore_backup()` | Rollback on failure |
| `get_update_status()` | Current update state |
| `compare_versions(v1, v2)` | Version comparison |

**Update Flow:**
```
check_for_updates()
  ↓
compare with current version (1.4.17)
  ↓
if update available:
  create_backup()
    ↓
  download_update()
    ↓
  verify_integrity(checksum)
    ↓
  install_update()
    ↓
  verify_success()
    ↓
  on failure: restore_backup()
```

**Configuration:**
```json
{
  "auto_check_enabled": true,
  "check_interval_hours": 24,
  "auto_install_enabled": false,
  "backup_before_update": true,
  "update_channel": "stable",
  "last_check": "2025-10-22T00:00:00",
  "update_server_url": "http://localhost:8989/api/updates"
}
```

---

### 7. **src/monitoring.py** - Performance Monitoring

**Purpose:** Track system metrics and application performance

#### PerformanceMonitor Class

**Metrics Collected:**

| Metric | Interval | Description |
|--------|----------|-------------|
| `cpu_usage` | 30s | System CPU percentage |
| `memory_usage` | 30s | System memory percentage |
| `memory_available` | 30s | Available RAM in GB |
| `disk_usage` | 30s | Disk space percentage |
| `process_cpu` | 30s | Shakshuka CPU usage |
| `process_memory` | 30s | Shakshuka memory in MB |

**Thresholds & Alerts:**

| Metric | Threshold | Severity |
|--------|-----------|----------|
| CPU | 80% | Warning |
| Memory | 80% | Warning |
| Disk | 90% | Critical |
| Response Time | 2 seconds | Warning |
| Error Rate | 5% | Warning |

**Methods:**

| Method | Purpose |
|--------|---------|
| `record_metric(name, value)` | Log metric data point |
| `record_timing(operation, duration)` | Track operation duration |
| `get_metrics()` | Retrieve all collected metrics |
| `get_health_status()` | Overall system health |
| `create_alert(type, message, severity)` | Generate system alert |
| `get_alerts()` | Retrieve active alerts |
| `get_performance_summary()` | JSON performance report |

**Storage:**
- Last 1000 entries per metric (memory-efficient)
- Circular buffer (deque with maxlen)
- Thread-safe with RLock

---

## Frontend Architecture

### Static Files Location
```
assets/
├── static/
│   ├── css/
│   │   ├── style.css          # Main styling
│   │   ├── tasks.css          # Task-specific styles
│   │   ├── planner.css        # Planner UI
│   │   └── responsive.css     # Mobile/tablet
│   ├── js/
│   │   ├── app.js             # Main app logic
│   │   ├── auth.js            # Authentication handling
│   │   ├── state.js           # State management
│   │   ├── utils.js           # Helper functions
│   │   └── api.js             # API client
│   └── images/
│       └── favicon.ico
└── templates/
    └── index.html             # Single-page app template
```

### Frontend API Client

**Base URL:** `http://127.0.0.1:8989/api`

**Authentication:** Session cookie + CSRF token

**Error Handling:**
```javascript
// Standard error response
{
  "error": "error message",
  "details": {/* error details */},
  "code": "ERROR_CODE"
}
```

---

## Security Features

### 1. **Input Sanitization**
- XSS prevention via HTML escaping
- Script tag removal
- Dangerous character filtering
- Max length enforcement (1000 chars default)

### 2. **Rate Limiting**
- 100 requests per 5 minutes per IP
- Automatic IP blocking on threshold exceed
- Memory-efficient deque-based tracking
- Auto-cleanup every 10 minutes

### 3. **Session Management**
- Secure random token generation (32 bytes)
- 24-hour expiration
- CSRF token per request (15-min TTL)
- Automatic session cleanup

### 4. **Password Security**
- bcrypt hashing (salt rounds: 12)
- Fallback to SHA256 if bcrypt unavailable
- Auto-upgrade on login
- Change password endpoint

### 5. **Transport Security**
- HTTPS ready (behind reverse proxy)
- Security headers:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Cache-Control: no-cache, no-store, must-revalidate`

### 6. **Data Encryption**
- Fernet symmetric encryption (cryptography library)
- PBKDF2 key derivation from password
- Local storage in encrypted files
- Database-level support

---

## Performance Optimization

### 1. **Auto-Save Mechanism**
- Background thread (30-second intervals)
- Configurable interval: 15s - 5 minutes
- Graceful shutdown with stop event
- Change detection to avoid redundant saves

### 2. **Database Optimization**
- Indexed lookups on frequent queries
- WAL mode for concurrent access
- Connection pooling with thread-safe manager
- Foreign key constraints for referential integrity

### 3. **Memory Management**
- Rate limiter cleanup every 10 minutes
- Token expiration automatic cleanup
- Circular buffers for metrics (1000 max entries)
- Daemon threads for background tasks

### 4. **Caching**
- Static asset caching headers
- CORS pre-flight optimization
- Session secret caching per user

---

## Error Handling & Logging

### Logging Levels

| Level | Usage |
|-------|-------|
| INFO | Normal operations, startup sequence |
| WARNING | Rate limiting, missing optional deps |
| ERROR | Database errors, save failures |

**Log Location:** `C:\Users\{user}\AppData\Roaming\Shakshuka\logs\shakshuka.log` (Windows)

### Error Response Format

```json
{
  "error": "Human-readable message",
  "details": {
    "field": "error details"
  },
  "code": "ERROR_CODE",
  "status": 400
}
```

### Common Error Codes

| Code | HTTP | Meaning |
|------|------|---------|
| `INVALID_CREDENTIALS` | 401 | Login failed |
| `SESSION_EXPIRED` | 401 | Session invalid/expired |
| `CSRF_INVALID` | 403 | CSRF token missing/invalid |
| `RATE_LIMIT_EXCEEDED` | 429 | Too many requests |
| `INVALID_TASK_DATA` | 400 | Task validation failed |
| `UNAUTHORIZED` | 403 | Insufficient permissions |
| `DATABASE_ERROR` | 500 | Database operation failed |
| `UPDATE_ERROR` | 500 | Update installation failed |

---

## Build & Deployment

### Build Tools

**PyInstaller Configuration:**
- Entry point: `main.py`
- Output: Single executable
- Includes: All assets, config, templates
- Hidden imports configured

**Build Command:**
```bash
python scripts/build.py
```

**Output:** `Shakshuka.exe` (Windows standalone executable)

### Windows Installation

**Methods:**
1. **Portable:** `Shakshuka.exe` (run directly, no install)
2. **Installer:** `Shakshuka-Setup-v1.4.17.exe` (InnoSetup installer)
3. **From Source:** `python main.py`

### Installer Script (InnoSetup)

**Features:**
- Start menu shortcuts
- Desktop shortcut
- Autostart registry entry (optional)
- Uninstall with data preservation option

---

## Dependency Stack

### Core Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Flask | 2.3.3 | Web framework |
| Flask-CORS | 4.0.0 | CORS handling |
| Werkzeug | 2.3.7 | WSGI utilities |
| cryptography | 41.0.7 | Data encryption |
| bcrypt | 4.0.1 | Password hashing |
| sqlite3 | Built-in | Database |
| pyinstaller | 6.16.0 | Build executable |
| pystray | 0.19.5 | System tray |
| Pillow | 10.4.0 | Image handling |
| psutil | 5.9.6 | System monitoring |
| schedule | 1.2.0 | Task scheduling |
| pywin32 | 311 | Windows integration |

---

## Configuration & Customization

### Environment Setup

**User Data Directory:**
```
Windows: C:\Users\{username}\AppData\Roaming\Shakshuka
Linux: ~/.shakshuka
macOS: ~/Library/Application Support/Shakshuka
```

### Configuration Files

**version.json:**
```json
{
  "version": "1.4.17",
  "build": "31",
  "release_date": "2025-10-22T00:20:00.000000",
  "update_channel": "stable"
}
```

**update_config.json:**
```json
{
  "auto_check_enabled": true,
  "check_interval_hours": 24,
  "auto_install_enabled": false,
  "backup_before_update": true,
  "update_channel": "stable"
}
```

---

## Testing

### Test Files

| File | Purpose |
|------|---------|
| `tests/run_tests.py` | Test runner |
| `tests/test_unit.py` | Unit tests |
| `tests/test_integration.py` | Integration tests |

### Running Tests

```bash
python tests/run_tests.py
```

---

## System Requirements

- **OS:** Windows 10/11 (primary), Linux/macOS with limitations
- **Python:** 3.8+ (for source execution)
- **RAM:** 512 MB minimum
- **Storage:** 50 MB (application) + data
- **Python Packages:** Specified in `config/requirements.txt`

---

## Known Limitations & Considerations

1. **Windows-Specific:**
   - System tray requires pystray + PIL
   - Autostart uses Windows registry
   - Path handling optimized for Windows

2. **Database:**
   - Single user per installation (currently)
   - SQLite suitable for local development/small deployments
   - No built-in replication

3. **Performance:**
   - Auto-save interval minimum 15 seconds
   - In-memory metrics limited to 1000 entries per metric
   - Rate limiter tracks up to 1000 IPs

4. **Security:**
   - No multi-user authentication (single user per machine)
   - HTTPS not enabled by default (reverse proxy recommended)
   - Data encryption optional (file storage unencrypted by default)

---

## Future Enhancement Opportunities

1. Multi-user support with proper authentication
2. Cloud sync capabilities
3. Mobile app (native iOS/Android)
4. Advanced analytics dashboard
5. Recurring tasks automation
6. Integration with calendar services (Google, Outlook)
7. Webhook support for external integrations
8. Real-time collaboration (WebSocket)
9. Full-text search capabilities
10. Machine learning task recommendations

---

## Troubleshooting Guide

### Common Issues

**Port 8989 already in use:**
- Solution: Modify port in `src/app.py` line 101
- Or: Kill process on port 8989

**Permission denied on Windows:**
- Solution: Run as Administrator
- Check Windows Defender exclusions

**Build fails:**
- Solution: Verify PyInstaller installation
- Check Python version (3.8+ required)
- Install all dependencies: `pip install -r config/requirements.txt`

**Database locked error:**
- Solution: Ensure no other instances running
- Check task manager for background Shakshuka process
- Restart application

**System tray not working:**
- Solution: Install pystray: `pip install pystray`
- Verify PIL/Pillow: `pip install Pillow`

---

## Contributing & Development

### Development Setup

1. Clone repository
2. Create virtual environment: `python -m venv venv`
3. Activate venv: `venv\Scripts\activate` (Windows)
4. Install deps: `pip install -r config/requirements.txt`
5. Run: `python main.py`

### Code Style

- PEP 8 compliant
- Type hints used throughout
- Docstrings for all major functions/classes
- Comments for complex logic

### Testing Before Commit

```bash
python tests/run_tests.py
# Check linting, coverage, etc.
```

---

## License & Attribution

**License:** MIT (Open Source)

**Created:** 2024-2025

**Contributors:** See CONTRIBUTING.md

---

**Last Updated:** October 22, 2025
**Code Version:** 1.4.17
**Document Version:** 1.0

