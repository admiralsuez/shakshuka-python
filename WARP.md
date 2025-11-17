# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

**Shakshuka** is a modern, privacy-focused Windows desktop task management application built with Python Flask backend and vanilla JavaScript frontend. The application runs entirely locally with no cloud dependencies, featuring task management, daily planning, analytics, and system tray integration.

**Current Version:** 3.0.6 (build 3)
**Platform:** Windows 10/11 (64-bit)
**Tech Stack:** Python 3.13, Flask 2.3.3, SQLite, Vanilla JavaScript (ES6+)

---

## Common Development Commands

### Running the Application

```powershell
# Development mode (from source)
python main.py

# The app will start on http://127.0.0.1:8989
```

### Building

```powershell
# Build standalone executable
python scripts\build.py

# The executable will be created as Shakshuka.exe in the root directory
```

### Testing

```powershell
# Run all tests
python tests\run_tests.py

# Run specific test file
python -m unittest tests.test_unit
python -m unittest tests.test_integration
```

### Installing Dependencies

```powershell
# Install all dependencies
pip install -r config\requirements.txt

# For development, ensure you're in a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r config\requirements.txt
```

### Linting and Type Checking

Note: This project does not currently have linting or type checking configured. Consider adding:
- `black` or `autopep8` for Python formatting
- `pylint` or `flake8` for Python linting
- `mypy` for Python type checking
- `eslint` for JavaScript linting

---

## Architecture Overview

### High-Level Architecture

Shakshuka follows a **modular monolithic architecture** with clear separation of concerns:

```
┌─────────────────────────────────────────────────────────────┐
│                      Browser (Client)                       │
│        HTML/CSS + Vanilla JavaScript (No Framework)         │
└─────────────────────────┬───────────────────────────────────┘
                          │ HTTP/REST API
┌─────────────────────────▼───────────────────────────────────┐
│                   Flask Web Server                          │
│  ┌──────────────────────────────────────────────────────┐   │
│  │          Main Application (src/app.py)               │   │
│  │   - Routes (40+ REST endpoints)                      │   │
│  │   - Business Logic                                   │   │
│  │   - Middleware (CSRF, Auth - currently disabled)     │   │
│  └──────────────────────┬───────────────────────────────┘   │
│                         │                                    │
│  ┌──────────────────────▼───────────────────────────────┐   │
│  │         Core Modules (src/)                          │   │
│  │  - SQLiteDataManager: Database operations            │   │
│  │  - SecurityManager: Security utilities               │   │
│  │  - UpdateManager: Auto-update system                 │   │
│  │  - UserManager: User management (optional)           │   │
│  │  - Monitoring: Performance tracking                  │   │
│  └──────────────────────┬───────────────────────────────┘   │
└─────────────────────────┼───────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│              SQLite Database (Local)                        │
│  - tasks: Task data with scheduling                         │
│  - users: User accounts (optional auth)                     │
│  - sessions: Session management                             │
│  - settings: Application settings                           │
└─────────────────────────────────────────────────────────────┘
```

### Critical Architectural Decisions

1. **Authentication is DISABLED by default**
   - The `@require_auth` and `@require_csrf` decorators exist but are no-ops
   - The application is designed for single-user, local-only operation
   - If you need to re-enable auth, search for "authentication disabled" comments in `src/app.py`

2. **Thread-Safe Operations**
   - Uses `threading.RLock()` for data manager and auto-save operations
   - Auto-save runs every 30 seconds in a background thread
   - Task scheduler uses the `schedule` library for daily resets

3. **Modular JavaScript Architecture (v3.0.0+)**
   - Code is being progressively modularized from a large `app.js` (~4300 lines)
   - New modules in `assets/static/js/core/`, `features/`, `modules/`, `utils-new/`
   - Maintains backward compatibility with global function exports

---

## Project Structure

```
shakshuka-python-final3/
├── main.py                          # Entry point - delegates to launcher
├── src/                             # Python backend
│   ├── app.py                       # Main Flask app (3000+ lines)
│   ├── sqlite_data_manager.py       # Database layer
│   ├── security_manager.py          # Security utilities
│   ├── update_manager.py            # Auto-update system
│   ├── user_manager.py              # User management
│   ├── monitoring.py                # Performance monitoring
│   ├── core/
│   │   ├── launcher.py              # Application launcher
│   │   ├── config.py                # Configuration constants
│   │   └── app_context.py           # Application state
│   ├── middleware/                  # Auth & CSRF (disabled)
│   ├── utils/                       # Validators & sanitizers
│   └── routes/                      # API routes (modular)
├── assets/
│   ├── static/
│   │   ├── css/                     # Stylesheets (style.css ~5000 lines)
│   │   ├── js/
│   │   │   ├── app.js               # Main app logic (~4300 lines)
│   │   │   ├── auth.js              # Auth handling (disabled)
│   │   │   ├── tasks.js             # Task operations
│   │   │   ├── utils.js             # Utility functions
│   │   │   ├── state.js             # State management
│   │   │   ├── core/                # Core modules (keyboard, app-init)
│   │   │   ├── features/            # Feature modules (settings)
│   │   │   ├── modules/             # UI modules (planner-v2, analytics)
│   │   │   └── utils-new/           # New utilities (error-handler)
│   │   └── images/                  # Assets and icons
│   └── templates/
│       └── index.html               # Single-page application
├── config/
│   ├── requirements.txt             # Python dependencies
│   ├── version.json                 # Version info (auto-updated)
│   └── changelog.txt                # Changelog
├── data/                            # SQLite DB and user data (created at runtime)
├── scripts/                         # Build and deployment scripts
│   ├── build.py                     # PyInstaller build script
│   ├── create-installer.py          # Inno Setup installer
│   └── create-professional-installer.py
├── tests/                           # Test suite
│   ├── run_tests.py                 # Test runner
│   ├── test_unit.py                 # Unit tests
│   └── test_integration.py          # Integration tests
└── tools/
    └── autostart.py                 # Windows autostart manager
```

---

## Key Subsystems

### 1. Database Layer (`src/sqlite_data_manager.py`)

- **Thread-safe** SQLite operations with WAL mode
- **Tables:** `tasks`, `users`, `sessions`, `settings`
- **Key Indexes:** Performance indexes on `completed`, `priority`, `due_date`, `scheduled_hour`
- **CRUD Operations:** All task operations go through `SQLiteDataManager`
- **Auto-save:** Background thread saves changes every 30 seconds

**Important Methods:**
- `create_task(task_data)`: Create new task
- `update_task(task_id, task_data)`: Update existing task
- `get_all_tasks(user_id=None)`: Retrieve all tasks
- `delete_task(task_id)`: Delete task
- `schedule_task(task_id, hour, duration, date)`: Schedule task in planner

### 2. Frontend Architecture

The frontend is **transitioning from monolithic to modular**:

**Legacy (still active):**
- `app.js`: Main application logic (~4300 lines) - being broken down
- Contains: Task CRUD, UI management, event handlers, state management

**New Modular Structure (v3.0.0+):**
- `core/app-init.js`: Application initialization
- `core/keyboard.js`: Keyboard shortcuts (Escape, N, Ctrl+N, Ctrl+S)
- `features/settings.js`: Settings management (extracted from app.js)
- `modules/planner-v2.js`: Daily planner with drag-and-drop
- `modules/analytics.js`: Analytics dashboard
- `utils-new/error-handler.js`: Global error handling with retry logic

**State Management:**
- `state.js`: Simple global state using `AppState.set()` / `AppState.get()`
- No framework - vanilla JavaScript with manual DOM manipulation

### 3. Task Scheduling System

**Daily Planner:**
- Time-grid based scheduling (24-hour view with 30-min slots)
- Drag-and-drop task scheduling
- Tasks can be scheduled for specific dates
- `scheduled_hour` format: "HH:MM" (e.g., "09:30")
- `scheduled_date` format: "YYYY-MM-DD"

**Important:** The planner-v2.js has had recent bug fixes related to:
- Hour format (must be "HH:MM" string, not numbers)
- Date filtering (tasks scheduled for other dates should remain available)

### 4. Strike System (Gamification)

- **Strike Today:** Mark task completed for today (can undo)
- **Strike Forever:** Permanently complete task (can undo)
- **Strike Counter:** Tracks daily completions
- **Analytics:** Displays strike streaks and productivity metrics

### 5. Build System (`scripts/build.py`)

**PyInstaller Configuration:**
- Single-file executable (`--onefile`)
- Console mode for debugging (`--console`)
- Includes: assets, templates, data, version.json
- 40+ `--hidden-import` flags for all dependencies
- Auto-increments build number in `config/version.json`

**Installer (Inno Setup):**
- Professional installer with uninstaller
- Installs to Program Files
- User data in `%APPDATA%\Shakshuka`
- Registry entries for autostart
- Process management during install/uninstall

---

## Important Patterns and Conventions

### Backend (Python)

1. **Error Handling:** Use try-except blocks with logging
   ```python
   try:
       result = operation()
   except Exception as e:
       logger.error(f"Operation failed: {e}")
       return jsonify({'error': str(e)}), 500
   ```

2. **API Responses:** Always return JSON with status codes
   ```python
   return jsonify({'success': True, 'data': result}), 200
   return jsonify({'error': 'Error message'}), 400
   ```

3. **Thread Safety:** Always use locks for shared resources
   ```python
   with self._lock:
       # Critical section
   ```

### Frontend (JavaScript)

1. **Module Pattern:** New code should follow the module pattern
   ```javascript
   const MyModule = {
       init() { /* ... */ },
       method() { /* ... */ }
   };
   // Backward compatibility
   window.myGlobalFunction = MyModule.method;
   ```

2. **Error Handling:** Use `ErrorHandler.safeAsync()` for API calls
   ```javascript
   const data = await ErrorHandler.safeAsync(
       () => fetch('/api/endpoint'),
       'Failed to load data'
   );
   ```

3. **State Management:** Use `AppState` for global state
   ```javascript
   AppState.set('currentDate', new Date());
   const date = AppState.get('currentDate');
   ```

4. **DOM Manipulation:** Check element existence before using
   ```javascript
   const element = document.getElementById('myElement');
   if (element) {
       element.classList.add('active');
   }
   ```

---

## Common Issues and Solutions

### Issue: "Cannot access local variable 'user_data_dir'"
**Solution:** Always call `get_user_data_dir()` within function scope, don't rely on module-level variable.

### Issue: "CSRF token validation failed"
**Solution:** Authentication is disabled. If you see this, ensure `@require_csrf` decorators are removed or disabled.

### Issue: "Tasks not appearing in planner after drag-and-drop"
**Solution:** Check that `scheduled_hour` is formatted as "HH:MM" string (e.g., "09:30"), not as numbers.

### Issue: "Available tasks disappear when changing dates"
**Solution:** Ensure filter checks if task is scheduled for the CURRENT selected date, not ANY date.

### Issue: "TypeError: task.scheduled_hour.split is not a function"
**Solution:** Convert `scheduled_hour` to string before calling `.split()`: `String(task.scheduled_hour).split(':')`

### Issue: "sqlite3.Row object has no attribute 'get'"
**Solution:** Use bracket notation with key existence checks:
```python
'field': row['field'] if 'field' in row.keys() else default_value
```

---

## Data Storage Locations

### Development Mode
- Database: `data/shakshuka.db`
- Logs: `data/logs/shakshuka.log`
- Settings: `data/settings.json`

### Production Mode (Installed)
- User Data: `%APPDATA%\Shakshuka\` (Windows)
- Database: `%APPDATA%\Shakshuka\data\shakshuka.db`
- Logs: `%APPDATA%\Shakshuka\logs\shakshuka.log`
- Flask Secret: `%APPDATA%\Shakshuka\.flask_secret`

**Important:** Never write to Program Files - always use `get_user_data_dir()`

---

## Performance Considerations

1. **Auto-save runs every 30 seconds** - avoid triggering manual saves unnecessarily
2. **Database uses WAL mode** - concurrent reads are safe
3. **SQLite indexes** - Query on `completed`, `priority`, `due_date`, `scheduled_hour` are optimized
4. **Frontend scrolling** - GPU-accelerated with `will-change` and `translateZ(0)`
5. **Modal animations** - Hardware-accelerated with reduced duration (0.2s)

---

## Modularization Roadmap (In Progress)

The project is actively being refactored from a monolithic `app.js` to modular architecture:

**Completed:**
- ✅ Error handling (`utils-new/error-handler.js`)
- ✅ Keyboard shortcuts (`core/keyboard.js`)
- ✅ App initialization (`core/app-init.js`)
- ✅ Settings management (`features/settings.js`)

**Planned:**
- ⏳ Modal management
- ⏳ Task management (extract from app.js)
- ⏳ Form handling
- ⏳ Drag-and-drop utilities
- ⏳ Analytics module (partially done)

**Goal:** Reduce `app.js` from ~4300 lines to <2000 lines while maintaining 100% backward compatibility.

---

## Version Management

Version information is stored in `config/version.json`:
```json
{
  "version": "3.0.6",
  "build": "3",
  "release_date": "2025-10-26T00:11:53.198228",
  "update_channel": "stable"
}
```

- **Build number auto-increments** when running `scripts/build.py`
- **Version is injected** into templates dynamically for cache busting
- **Changelog** maintained in `config/changelog.txt`

---

## Testing Strategy

### Test Execution
```powershell
python tests\run_tests.py
```

### Test Coverage
- **Unit Tests:** Database operations, security, monitoring, user management
- **Integration Tests:** API endpoints, performance testing
- **Success Criteria:** >90% pass rate

### Manual Testing Checklist
- [ ] Create task (Quick Add, Full Form, Schedule)
- [ ] Edit task
- [ ] Delete task
- [ ] Mark task as completed (Strike Today, Strike Forever)
- [ ] Undo strike
- [ ] Schedule task in planner (drag-and-drop)
- [ ] Navigate between pages (Tasks, Planner, Analytics, Settings)
- [ ] Change theme and settings
- [ ] Import/Export tasks
- [ ] System tray functionality
- [ ] Autostart configuration

---

## Security Notes

1. **Authentication is disabled** - This is a single-user local application
2. **No cloud connectivity** - All data stays local
3. **CSRF protection exists but is disabled** - Can be re-enabled if needed
4. **SQL injection protection** - All queries use parameterized statements
5. **XSS protection** - HTML escaping on all user inputs

---

## Debugging Tips

1. **Console logs:** The app has 109+ console.log statements (some cleaned in v3.0.0)
2. **Flask debug mode:** Disabled in production for security
3. **Logging:** Check `%APPDATA%\Shakshuka\logs\shakshuka.log` for detailed logs
4. **Browser DevTools:** Use Network tab to inspect API calls
5. **Database:** Use SQLite browser to inspect `shakshuka.db` directly

---

## Additional Resources

- **Build Reports:** `build_reports/` - Detailed build logs and changelogs
- **Old Version Backup:** `Shakshuka-v2.0.0-Clean-Backup/` - Reference for v2.0.0
- **Documentation:** `Shakshuka-v2.0.0-Clean-Backup/docs/` - Installation, troubleshooting guides
