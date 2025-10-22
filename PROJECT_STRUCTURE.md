# Shakshuka Project Structure

## 📁 Root Directory Organization

```
shakshuka-python-final3/
├── 📄 main.py                          # Application entry point
├── 📄 Shakshuka.exe                    # Standalone executable (latest build)
├── 📄 Shakshuka-Setup-v1.5.0-b36.exe  # Latest installer
├── 📄 git.json                         # Git configuration
├── 📄 json.txt                         # JSON utilities
│
├── 📁 assets/                          # Frontend assets
│   ├── static/
│   │   ├── css/                       # Stylesheets
│   │   ├── fonts/                     # Font files
│   │   ├── images/                    # Images and icons
│   │   ├── js/                        # JavaScript files
│   │   │   ├── app.js                # Main application logic
│   │   │   ├── auth.js               # Authentication
│   │   │   ├── state.js              # State management
│   │   │   ├── tasks.js              # Task management
│   │   │   ├── utils.js              # Utilities
│   │   │   └── modules/              # ✨ NEW: Modular JS
│   │   │       ├── ui.js             # UI components
│   │   │       ├── settings.js       # Settings management
│   │   │       ├── planner.js        # Daily planner
│   │   │       └── analytics.js      # Analytics & charts
│   │   └── webfonts/                 # Web fonts
│   └── templates/
│       ├── index.html                # Main SPA template
│       └── components/               # Template components
│
├── 📁 build_reports/                   # Auto-generated build reports
│   ├── BUILD_REPORT_v1.4.18.md
│   ├── BUILD_REPORT_v1.5.0-b33.md
│   ├── BUILD_REPORT_v1.5.0-b34.md
│   └── BUILD_REPORT_v1.5.0-b36.md
│
├── 📁 config/                          # Configuration files
│   ├── changelog.txt                  # Version changelog
│   ├── requirements.txt               # Python dependencies
│   └── version.json                   # Version information
│
├── 📁 data/                            # User data
│   ├── backups/                       # Automatic backups
│   ├── sessions.json                  # User sessions
│   ├── update_config.json             # Update settings
│   └── users.json                     # User accounts
│
├── 📁 documentation/                   # ✨ All documentation files
│   ├── BLANK_PAGE_FIX.md
│   ├── BUG_FIX_REPORT.md
│   ├── CACHE_BUSTER_FIX.md
│   ├── CODE_ANALYSIS.md
│   ├── CURSOR_README.md
│   ├── DISTRIBUTABLE_READY.md
│   ├── EXECUTABLES_COMPARISON.md
│   ├── FINAL_FIX_TASKS_LOADERROR.md
│   ├── PROJECT_SUMMARY.md
│   ├── REFACTORING_COMPLETE.md
│   ├── REFACTORING_PLAN.md
│   ├── REFACTORING_SUMMARY.md
│   ├── SETTINGS_SAVE_BUG_FIX.md
│   ├── THEME_PERSISTENCE_FIX.md
│   └── VERSION_UPGRADE_NOTE.md
│
├── 📁 docs/                            # Official documentation
│   ├── INSTALLATION.md
│   ├── LICENSE.txt
│   ├── README.md
│   └── TROUBLESHOOTING.md
│
├── 📁 logs/                            # Application logs
│   └── shakshuka.log
│
├── 📁 releases/                        # ✨ Previous release builds
│   ├── Shakshuka-Setup-v1.5.0-b33.exe
│   └── Shakshuka-Setup-v1.5.0-b34.exe
│
├── 📁 scripts/                         # Build and utility scripts
│   ├── build.py                       # Main build script
│   ├── build.bat                      # Windows build wrapper
│   ├── build-installer.bat            # Installer build wrapper
│   ├── installer.iss                  # Inno Setup script
│   ├── Start-Shakshuka.bat           # Launch script
│   ├── Start-Shakshuka-Silent.bat    # Silent launch
│   ├── Start-Shakshuka-Verbose.bat   # Verbose launch
│   ├── Stop-Shakshuka.bat            # Stop script
│   └── dist/                          # Build output
│       └── Shakshuka-Setup-v1.5.0-b36.exe
│
├── 📁 src/                             # Python source code
│   ├── __init__.py
│   ├── app.py                         # Main Flask application
│   ├── app_factory.py                 # Application factory
│   ├── api_docs.py                    # API documentation
│   ├── monitoring.py                  # System monitoring
│   ├── security_manager.py            # Security utilities
│   ├── sqlite_data_manager.py         # Database operations
│   ├── update_manager.py              # Update management
│   ├── user_manager.py                # User management
│   │
│   ├── app_core/                      # Legacy core (to be deprecated)
│   │   ├── dirs.py
│   │   └── settings.py
│   │
│   ├── core/                          # ✨ NEW: Core modules
│   │   ├── __init__.py
│   │   ├── app_context.py            # Application state
│   │   ├── config.py                 # Configuration
│   │   └── launcher.py               # Launch orchestration
│   │
│   ├── middleware/                    # ✨ NEW: Middleware
│   │   ├── __init__.py
│   │   ├── auth_middleware.py        # Authentication
│   │   └── csrf_middleware.py        # CSRF protection
│   │
│   ├── routes/                        # ✨ NEW: Route blueprints (ready)
│   │   └── __init__.py
│   │
│   ├── utils/                         # ✨ NEW: Utilities
│   │   ├── __init__.py
│   │   ├── sanitizers.py             # Input sanitization
│   │   └── validators.py             # Input validation
│   │
│   └── data/                          # SQLite database
│       └── shakshuka.db
│
├── 📁 tests/                           # Test suite
│   ├── run_tests.py
│   ├── test_integration.py
│   └── test_unit.py
│
├── 📁 tools/                           # System tools
│   ├── __init__.py
│   ├── autostart.py                   # Windows autostart manager
│   ├── install.ps1                    # Installation script
│   ├── uninstall.ps1                  # Uninstallation script
│   ├── server-manager.ps1             # Server management
│   └── server-manager-gui.py          # GUI server manager
│
└── 📁 updates/                         # Update staging area
    └── src/data/shakshuka.db
```

## 🎯 Key Directories

### Production Files (Root)
- `Shakshuka.exe` - Current standalone executable
- `Shakshuka-Setup-v1.5.0-b36.exe` - Current installer

### New Modular Structure
- `src/core/` - Core application components (config, context, launcher)
- `src/middleware/` - Request/response middleware (auth, CSRF)
- `src/utils/` - Reusable utilities (validators, sanitizers)
- `assets/static/js/modules/` - Modular JavaScript (UI, settings, planner, analytics)

### Organized Documentation
- `documentation/` - All technical documentation and fix reports
- `docs/` - Official user-facing documentation
- `build_reports/` - Automated build reports

### Build Artifacts
- `releases/` - Previous version installers
- `scripts/dist/` - Latest build output

## 📝 Clean Structure Benefits

✅ **No scattered MD files in root**
✅ **Old builds moved to releases/**
✅ **All documentation in documentation/**
✅ **Build reports in dedicated folder**
✅ **Modular code structure**
✅ **Clear separation of concerns**

## 🔄 Version Control

Current Version: **v1.5.0 build 36**
- Auto-increments on each build
- Version tracked in `config/version.json`
- Build reports auto-generated in `build_reports/`

## 🎨 Code Organization

### Backend (Python)
- **Monolithic**: `src/app.py` (2,993 lines - main Flask app)
- **Modular**: `src/core/`, `src/middleware/`, `src/utils/` (901 lines total)

### Frontend (JavaScript)
- **Main**: `assets/static/js/app.js` (4,647 lines)
- **Modular**: `assets/static/js/modules/` (963 lines across 4 modules)

## 📦 Build System

- Build script: `scripts/build.py`
- Installer: Inno Setup 6 (`scripts/installer.iss`)
- Output: Both standalone `.exe` and installer
- Reports: Auto-generated in `build_reports/`

---

**Structure Last Updated**: October 22, 2025 (v1.5.0-b36)

