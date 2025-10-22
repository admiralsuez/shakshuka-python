# CURSOR IDE Guide for Shakshuka Project

## Quick Start for Cursor Development

This guide helps you understand and work with the Shakshuka task management application in Cursor IDE.

---

## Project Overview

**Project Name:** Shakshuka - Modern Task Management Application  
**Type:** Python Flask Web Application  
**Version:** 1.4.17 (Build 31)  
**Primary Language:** Python 3.8+  
**Frontend:** HTML5, CSS3, JavaScript (ES6+)  
**Database:** SQLite3

### Project Statistics
- **Main Backend File:** `src/app.py` (~2800 lines)
- **Total Python Modules:** 7 core modules
- **API Routes:** 40+ endpoints
- **Database Tables:** 4 (users, tasks, settings, sessions)
- **Frontend Components:** Single-page application (SPA)

---

## Directory Structure for Cursor Navigation

### Critical Files to Know

```
📁 Workspace Root
├── 📄 main.py                      ⭐ Application entry point
├── 📁 src/
│   ├── 📄 app.py                   ⭐ Main Flask app (119+ functions)
│   ├── 📄 security_manager.py       ⭐ Rate limiting & input validation
│   ├── 📄 sqlite_data_manager.py    ⭐ Database management
│   ├── 📄 user_manager.py           ⭐ Authentication & sessions
│   ├── 📄 update_manager.py         ⭐ OTA updates
│   ├── 📄 monitoring.py             ⭐ Performance metrics
│   └── 📁 app_core/
│       ├── settings.py
│       └── dirs.py
├── 📁 assets/
│   ├── 📁 static/
│   │   ├── 📁 css/                  Frontend styling
│   │   ├── 📁 js/                   Frontend logic
│   │   └── 📁 images/
│   └── 📁 templates/
│       └── 📄 index.html            Main SPA template
├── 📁 config/
│   ├── 📄 requirements.txt          Python dependencies
│   ├── 📄 version.json              Version info
│   └── 📄 changelog.txt             Release notes
├── 📁 data/                         Auto-generated data storage
├── 📁 tools/                        Utility scripts
├── 📁 scripts/                      Build & deployment
├── 📁 tests/                        Test suite
├── 📁 docs/
│   └── 📄 README.md                 Main documentation
└── 📄 CODE_ANALYSIS.md              📖 Comprehensive code analysis

```

---

## Core Architecture in Cursor

### Understanding the Application Flow

**Startup Sequence (main.py → src/app.py):**

```
main.py
  ├─ setup_paths()                    # Path initialization
  ├─ initialize_data_manager()        # Database setup
  ├─ start_auto_save()                # Background thread (30s interval)
  ├─ start_scheduler()                # Daily reset jobs
  ├─ start_system_tray()              # Windows integration
  └─ Flask.run(host='127.0.0.1', port=8989)
```

### Key Classes to Understand

#### 1. **AppContext** (src/app.py, lines 133-288)
The centralized application state manager with thread safety.

**When to Use:** Understanding global state, session management, auto-save behavior

**Key Properties:**
- `data_manager` - SQLiteDataManager instance
- `auto_save_enabled` - Toggle auto-save
- `password_set` - Authentication state
- `csrf_tokens` - Security token storage

#### 2. **SQLiteDataManager** (src/sqlite_data_manager.py)
Thread-safe database operations with user-specific data isolation.

**Key Methods:**
- `add_task(user_id, task_data)` - Create task
- `get_tasks(user_id, filters)` - Retrieve tasks
- `update_task(task_id, updates)` - Modify task
- `backup_database()` - Full snapshot
- `restore_backup(backup_path)` - Restore from backup

#### 3. **SecurityManager** (src/security_manager.py)
Input sanitization, rate limiting, and session security.

**Key Methods:**
- `check_rate_limit(client_ip)` - 100 req/5 min per IP
- `sanitize_input(text)` - XSS prevention
- `get_rate_limit_stats()` - Usage tracking

#### 4. **UserManager** (src/user_manager.py)
User authentication and session management.

**Key Methods:**
- `create_user(username, password)` - Registration (bcrypt)
- `verify_user(username, password)` - Login
- `create_session(user_id)` - 24-hour session
- `cleanup_expired_sessions()` - Auto-cleanup

---

## Working with Cursor Features

### 1. **Code Search in Cursor**

**Find Route Handlers:**
```
Ctrl+F: "def api_" or "@app.route"
```

Example findings:
- `@app.route('/api/tasks', methods=['GET'])`
- `@app.route('/api/tasks/<task_id>/complete', methods=['POST'])`

**Find Database Operations:**
```
Ctrl+F: "def add_task" or "def get_tasks"
```

**Find Background Threads:**
```
Ctrl+F: "def auto_save_worker" or "def scheduler_worker"
```

### 2. **Using Cursor's Code Outline**

In Cursor, open the Outline panel (Ctrl+Shift+O) for:
- **src/app.py:** 119+ functions organized by category
- **Route Functions:** Group by `/api/` prefix
- **Decorators:** @require_auth, @require_csrf, @rate_limit
- **Middleware:** after_request, before_request handlers

### 3. **Running Code from Cursor**

**Run the Application:**
```bash
python main.py
```
The app launches at: http://127.0.0.1:8989

**Run Tests:**
```bash
python tests/run_tests.py
```

**Build Executable:**
```bash
python scripts/build.py
```

Output: `Shakshuka.exe`

### 4. **Debugging in Cursor**

**Set Breakpoints:**
- Click line numbers to add breakpoints
- Use Ctrl+Shift+D to open Debug panel

**Common Debugging Points:**
- `src/app.py:1687` - create_task() function
- `src/app.py:1458` - get_tasks() function
- `src/sqlite_data_manager.py:140` - _run_migrations()
- `src/security_manager.py:73` - check_rate_limit()

**Debug Configuration:**
Create `.vscode/launch.json`:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: Flask",
      "type": "python",
      "request": "launch",
      "module": "flask",
      "env": {"FLASK_APP": "main.py"},
      "args": ["run"],
      "jinja": true,
      "justMyCode": true
    }
  ]
}
```

---

## API Routes Reference for Cursor

### Authentication Routes
| Route | Method | File Location | Line |
|-------|--------|--------------|------|
| `/api/auth/login` | POST | src/app.py | 1308 |
| `/api/auth/logout` | POST | src/app.py | 1415 |
| `/api/auth/status` | GET | src/app.py | 1353 |
| `/verify-session` | POST | src/app.py | 1394 |

### Task Management Routes
| Route | Method | File Location | Line |
|-------|--------|--------------|------|
| `/api/tasks` | GET | src/app.py | 1458 |
| `/api/tasks` | POST | src/app.py | 1687 |
| `/api/tasks/<id>` | PUT | src/app.py | 1728 |
| `/api/tasks/<id>` | DELETE | src/app.py | 1776 |
| `/api/tasks/<id>/complete` | POST | src/app.py | 1818 |
| `/api/tasks/<id>/strike` | POST | src/app.py | 1836 |
| `/api/tasks/<id>/schedule` | POST | src/app.py | 1938 |

### Settings Routes
| Route | Method | File Location | Line |
|-------|--------|--------------|------|
| `/api/settings` | GET | src/app.py | 1995 |
| `/api/settings` | POST | src/app.py | 2077 |

### System Routes
| Route | Method | File Location | Line |
|-------|--------|--------------|------|
| `/api/health` | GET | src/app.py | 348 |
| `/api/metrics` | GET | src/app.py | 2246 |
| `/api/updates/check` | GET | src/app.py | 1006 |
| `/shutdown` | POST | src/app.py | 2583 |

---

## Database Schema

Access database structure in: `src/sqlite_data_manager.py:53-138`

### Tables Quick Reference

**users** (Primary user records)
```sql
id (TEXT, PK) | username (UNIQUE) | password_hash | is_active | created_at | updated_at
```

**tasks** (User tasks)
```sql
id (TEXT, PK) | user_id | title | description | project | priority 
| status | completed | completed_at | due_date | estimated_duration 
| scheduled_hour | scheduled_duration | struck_today | strike_count | ...
```

**settings** (User preferences)
```sql
user_id (PK) | theme | dpi_scale | autosave_interval | notifications | created_at | updated_at
```

**sessions** (Active sessions)
```sql
session_id (PK) | user_id | expires_at | created_at
```

### Indexes for Performance
- `idx_tasks_user_id` - Fast user task lookup
- `idx_tasks_status` - Filter by status
- `idx_tasks_completed` - Completed task retrieval

---

## Frontend File Guide

### CSS Files (assets/static/css/)
| File | Purpose |
|------|---------|
| `style.css` | Main styling, gradients, glass-morphism |
| `tasks.css` | Task-specific styles |
| `responsive.css` | Mobile/tablet responsive design |

### JavaScript Files (assets/static/js/)
| File | Purpose |
|------|---------|
| `app.js` | Main app logic, DOM management |
| `auth.js` | Login/logout, session handling |
| `state.js` | Client-side state management |
| `utils.js` | Helper functions, formatting |
| `api.js` | API client, fetch wrappers |

### HTML Template
| File | Purpose |
|------|---------|
| `index.html` | Single-page app container |

---

## Security Features to Review in Cursor

### 1. Input Sanitization
**File:** `src/security_manager.py`  
**Function:** `sanitize_input()`  
**Line:** ~53

Prevents XSS attacks through:
- HTML escaping
- Script tag removal
- Dangerous character filtering

### 2. Rate Limiting
**File:** `src/security_manager.py`  
**Function:** `check_rate_limit()`  
**Line:** ~73

- 100 requests per 5 minutes per IP
- Memory-efficient deque-based tracking
- Auto-cleanup every 10 minutes

### 3. CSRF Protection
**File:** `src/app.py`  
**Functions:** `generate_csrf_token()`, `validate_csrf_token()`  
**Lines:** ~210-238

- 15-minute token expiration
- Automatic cleanup of expired tokens

### 4. Session Security
**File:** `src/user_manager.py`  
**Function:** `create_session()`  
**Security:** 
- 32-byte secure random tokens
- 24-hour expiration
- Automatic cleanup

---

## Performance Monitoring

### Background Threads

**Auto-Save Worker:**
- File: `src/app.py`
- Function: `auto_save_worker()` (line ~657)
- Interval: 30 seconds (configurable 15s-5m)
- Operation: Saves tasks if changes detected

**Scheduler Worker:**
- File: `src/app.py`
- Function: `scheduler_worker()` (line ~788)
- Operations: Daily resets, session cleanup, backups

### Monitoring System

**File:** `src/monitoring.py`  
**Class:** `PerformanceMonitor`

Tracks:
- CPU usage (% and per-process)
- Memory usage (% and available GB)
- Disk usage (%)
- Response times
- Error rates

**Thresholds:**
- CPU: 80% warning
- Memory: 80% warning
- Disk: 90% critical

---

## Common Development Tasks

### Adding a New API Endpoint

**Location:** `src/app.py`

**Template:**
```python
@app.route('/api/new-endpoint', methods=['POST'])
@require_auth
@require_csrf
@rate_limit
def new_endpoint():
    """Endpoint description"""
    data = request.get_json()
    
    # Validate input
    data = sanitize_input(json.dumps(data))
    
    # Get user ID
    user_id = get_user_id()
    
    # Database operation
    result = app_context.data_manager.some_operation(user_id, data)
    
    # Response
    return jsonify({"success": True, "data": result}), 200
```

### Adding a Database Migration

**Location:** `src/sqlite_data_manager.py:140-200` (_run_migrations method)

**Process:**
1. Add migration function: `_migrate_v{number}()`
2. Update version tracking
3. Test rollback logic
4. Add backup creation before migration

### Debugging Database Issues

**Check Database:**
```python
# In Python shell
import sqlite3
conn = sqlite3.connect('C:\\Users\\{user}\\AppData\\Roaming\\Shakshuka\\data\\shakshuka.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM tasks LIMIT 5")
print(cursor.fetchall())
```

### Testing Code Changes

**Before committing:**
```bash
python tests/run_tests.py
python -m pytest tests/ -v
```

---

## Build & Release Process

### Local Build

1. **Prepare:**
   ```bash
   pip install -r config/requirements.txt
   ```

2. **Build Executable:**
   ```bash
   python scripts/build.py
   ```

3. **Output:** `Shakshuka.exe`

4. **Test Executable:**
   ```bash
./Shakshuka.exe
```

### Release Checklist

- [ ] Update version in `config/version.json`
- [ ] Update `config/changelog.txt`
- [ ] Run full test suite
- [ ] Build executable
- [ ] Test on clean Windows VM
- [ ] Create installer with InnoSetup
- [ ] Tag commit with version number
- [ ] Push to GitHub

---

## Dependency Management

### Install All Dependencies

```bash
pip install -r config/requirements.txt
```

### Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Flask | 2.3.3 | Web framework |
| cryptography | 41.0.7 | Encryption |
| bcrypt | 4.0.1 | Password hashing |
| pyinstaller | 6.16.0 | Executable builder |
| pystray | 0.19.5 | System tray |
| psutil | 5.9.6 | System monitoring |

### Adding New Dependencies

1. Install locally: `pip install package-name`
2. Add to `config/requirements.txt`
3. Test that it works
4. Rebuild executable
5. Commit changes

---

## Cursor-Specific Tips

### 1. Use Cursor's AI Features

**Ask Cursor to Explain:**
- "Explain the auto_save_worker function"
- "What does the SecurityManager.check_rate_limit method do?"
- "Walk me through task creation flow"

### 2. Code Completion

When typing in Flask routes:
- Type `@app.route` → Cursor suggests route decorators
- Type `@require_` → Cursor suggests auth decorators
- Type `app_context.` → Cursor shows all properties

### 3. Multi-File Editing

**Edit Workflow:**
1. Open `src/app.py` (main logic)
2. Open `src/sqlite_data_manager.py` (database operations)
3. Open `assets/static/js/app.js` (frontend)
4. Use split view (Ctrl+\) for side-by-side editing

### 4. Test in Cursor Terminal

**Terminal (Ctrl+`):**
```bash
# Run app
python main.py

# Run tests
python tests/run_tests.py

# Build
python scripts/build.py

# Check linting
python -m pylint src/app.py
```

---

## Git Workflow in Cursor

### Current Status
```
Branch: stable
Remote: up to date with origin/stable
```

### Modified Files (24 files)
- Core: `main.py`, `src/app.py`, `src/security_manager.py`, etc.
- Frontend: `assets/static/css/`, `assets/static/js/`, `index.html`
- Config: `config/version.json`, `config/changelog.txt`
- Scripts: Build and autostart scripts

### Recommended Commit Strategy

1. **Feature branches:** `feature/new-functionality`
2. **Bug fixes:** `bugfix/issue-number`
3. **Releases:** Tag with `v1.4.17`

**Example:**
```bash
git checkout -b feature/task-filtering
# Make changes
git add src/app.py assets/static/js/app.js
git commit -m "feat: Add task filtering by priority"
git push origin feature/task-filtering
# Create PR
```

---

## Troubleshooting in Cursor

### Port Already in Use
**File:** `src/app.py` line 101  
**Fix:** Change `port=8989` to different port

### Import Errors
**Common Issue:** Missing modules in `src/__init__.py`  
**Solution:**
```python
# src/__init__.py
from . import app
from . import sqlite_data_manager
from . import security_manager
from . import user_manager
from . import update_manager
from . import monitoring
```

### Database Lock
**Symptom:** "database is locked" error  
**Solution:**
1. Check for background Flask process
2. Restart application
3. Check for corrupted `.db-journal` file

### Static Files Not Loading
**Symptom:** CSS/JS 404 errors  
**File:** `src/app.py` lines 77-82  
**Check:**
- `static_dir` path points to `assets/static`
- `template_dir` path points to `assets/templates`

---

## Additional Resources

### In Repository
- **CODE_ANALYSIS.md** - Comprehensive code documentation (this repo)
- **docs/README.md** - User-facing documentation
- **docs/INSTALLATION.md** - Setup instructions
- **docs/TROUBLESHOOTING.md** - Common issues
- **config/changelog.txt** - Release history

### External Resources
- Flask Documentation: https://flask.palletsprojects.com/
- SQLite Documentation: https://www.sqlite.org/docs.html
- PyInstaller Guide: https://pyinstaller.org/
- Cursor IDE: https://www.cursor.com/

---

## Quick Reference

### File Size Overview
| File | Lines | Purpose |
|------|-------|---------|
| `src/app.py` | ~2800 | Main Flask app |
| `src/sqlite_data_manager.py` | ~1200 | Database |
| `src/user_manager.py` | ~250 | Auth |
| `src/security_manager.py` | ~150 | Security |
| `src/update_manager.py` | ~360 | Updates |
| `src/monitoring.py` | ~240 | Metrics |

### Key Keyboard Shortcuts in Cursor
| Shortcut | Action |
|----------|--------|
| Ctrl+F | Find |
| Ctrl+H | Replace |
| Ctrl+Shift+F | Find in files |
| Ctrl+Shift+O | Open outline |
| Ctrl+G | Go to line |
| F12 | Go to definition |
| Ctrl+K, Ctrl+X | Delete line |
| Ctrl+Alt+↑/↓ | Move line up/down |

---

**Last Updated:** October 22, 2025  
**For:** Cursor IDE  
**Project Version:** 1.4.17
