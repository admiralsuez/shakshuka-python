# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Overview

Shakshuka is a Flask-based desktop/web hybrid task manager. The Python backend runs a local HTTP server and is bundled into platform-specific executables (PyInstaller on Windows, .deb packages on Linux, .app/.dmg on macOS). Most current work and tooling is focused on Windows.

Key backend modules live under `src/` and serve HTML/JS/CSS from `assets/` and `templates/`. Data is stored in SQLite databases under a per-user data directory resolved by `src/utils/paths.py`.

For recent high-level changes, see the "Recent Work Summary" in `README.md`.

## Commands and workflows

### Install dependencies (Python backend)

- Windows (PowerShell):
  - `python -m pip install -r config/requirements.txt`
- Linux (backend only, no packaging):
  - `pip3 install -r config/requirements-linux.txt`

### Run the app from source (development)

- Start the Flask app and open the UI on `http://127.0.0.1:8989`:
  - Windows: `python main.py`
  - POSIX: `python3 main.py`

`main.py` is the only supported CLI entrypoint in development; it wires up paths and delegates to `src/core/launcher.py`.

### Build on Windows

Primary build path (auto-incrementing version/build, Windows-only):

- Ensure Python deps are installed:
  - `python -m pip install -r config/requirements.txt`
- Run the modular build script:
  - `python scripts\build.py`

`scripts/build.py` will:
- Run `scripts/exception_policy_check.py` (and the companion check if the Flutter project exists).
- Bump the two-part version in `config/version.json` and update `config/changelog.txt`.
- Build a PyInstaller executable and Inno Setup installer.
- Generate a markdown build report under `build_reports/`.

Resulting artifacts (see `README.md` for details):
- `dist/Shakshuka.exe` — standalone app.
- `dist/Shakshuka-Setup-vX.X.exe` — installer.

If you need to understand or tweak version bumping/installer wiring, inspect the `scripts/build/` helpers used by `scripts/build.py` plus `config/version.json` and `scripts/installer.iss`.

### Linux packaging

Linux `.deb` packaging is documented in `docs/BUILD-LINUX.md`. That guide assumes helper scripts like `scripts/build-deb.py` / `scripts/build-deb.sh` and `setup.py` are present or created; follow that document if you are extending the Linux packaging story.

For backend-only work on Linux/WSL, installing `config/requirements-linux.txt` and running `python3 main.py` is sufficient.

### Running tests

Canonical test runner:

- From the repo root:
  - `python tests\run_tests.py`

What it does:
- Aggregates unit tests from `tests/test_unit.py` and integration tests from `tests/test_integration.py`.
- Prints a summary with success rates and writes `test_report.json` in the current directory.
- Returns a non-zero exit code if overall success rate falls below 90%.

Running a subset of tests (standard `unittest` patterns):

- Single test module:
  - `python -m unittest tests.test_unit`
- Single test case:
  - `python -m unittest tests.test_unit.TestSQLiteDataManager`
- Single test method:
  - `python -m unittest tests.test_unit.TestSQLiteDataManager.test_task_operations`

### Exception policy check (lint-like guard)

Before or after making Python changes (especially in `src/`), run the custom exception policy checker used by the build script:

- `python scripts\exception_policy_check.py src`
- Strict mode (treats `except Exception` without `# noqa: broad-except` as violations):
  - `python scripts\exception_policy_check.py --strict src`

This enforces:
- No bare `except:`.
- `except Exception:` must be annotated with `# noqa: broad-except` if truly needed.
- No `except ...:` blocks whose only body is `pass`.

### Windows smoke-testing workflow

`docs/WINDOWS-TEST-GUIDE.md` contains a detailed, step-by-step guide (in Hindi/English) for:
- Installing dependencies on Windows.
- Running `python main.py` and verifying the console banner and browser behavior.
- Using WSL/VM/Cloud Linux environments if you need to build `.deb` packages from a Windows host.

Refer to that document for concrete manual test steps and troubleshooting commands.

## Architecture overview

### Runtime entrypoints and lifecycle

- `main.py`
  - Lightweight launcher that adjusts `sys.path` for dev vs PyInstaller, handles the `--shutdown` CLI flag, and delegates to `src/core/launcher.launch_application()`.
  - The `--shutdown` path sends an HTTP POST to `/api/shutdown` and, on Windows, falls back to `taskkill /IM Shakshuka.exe /T /F` if the port stays open.
- `src/core/launcher.py`
  - `ApplicationLauncher` orchestrates startup: sets paths, fixes console encoding, initializes the data manager, starts auto-save and scheduler, optionally starts the system tray, then starts the Flask server using `werkzeug.serving.run_simple`.
  - Also responsible for opening the browser once `/health` returns 200 and for starting/stopping the monitoring subsystem.

When running under PyInstaller, both `main.py` and the launcher handle `sys.frozen` correctly and read configuration from the bundle.

### Flask app and configuration

- `src/app_factory.py`
  - Owns creation of the Flask `app` object.
  - Loads configuration from `src/core/config.config` (which wraps `src/constants`) and enforces `MAX_CONTENT_LENGTH_BYTES`.
  - Uses `src/utils/paths.get_user_data_dir()` to locate a per-user writable directory and persists a secret key in `.flask_secret` there, with `FLASK_SECRET_KEY` as a fallback if the file cannot be created.
  - Installs correlation-ID middleware via `src/core/correlation.init_flask_middleware`.
- `src/app.py`
  - Imports the `Flask` app from `app_factory`, configures logging and static asset paths (`configure_assets`, `configure_working_dir`, `configure_logging` from `src/app_setup.py`).
  - Creates and wires a long-lived `AppContext` instance (from `src/core/app_context`) into the Flask app via `src.core.di.set_extension(app, 'app_context', ...)`.
  - Exposes `ensure_data_manager` and `get_user_id` as app extensions; `get_user_id` is currently hard-wired to `DEFAULT_USER_ID` (no multi-user auth).
  - Registers all blueprints from `src/routes/*` using explicit `init_*_routes` functions and dependency injection so the route modules remain relatively stateless.
  - Sets up global CORS using `ALLOWED_ORIGINS` from `src/constants` and a Content Security Policy header appropriate for the bundled assets.

For versioning, `_get_app_version()` in `src/app.py` is the canonical helper for reading `config/version.json` in both dev and frozen modes; health and update endpoints are expected to delegate to it rather than re-reading the file.

### AppContext, services, and background workers

- `AppContext` (defined in `src/app.py`, instance imported from `src/core/app_context`) centralizes mutable backend state:
  - `data_manager` (`SQLiteDataManager` instance).
  - `autostart_manager` (Windows autostart integration via `tools/autostart.WindowsAutostart`).
  - `pin_manager` (PIN-based auth/session management).
  - `update_manager` (self-updates and scheduled backups).
  - Auto-save state (flags, timestamps, task signatures) and CSRF token cache (`cachetools.TTLCache`).
- Auto-save and scheduling are handled via service modules under `src/services/`:
  - `autosave.py`: provides `start_auto_save` / `stop_auto_save` functions; `src/app.py` injects `app_context` and `get_user_id` into this module and lets it manage the background thread.
  - `scheduler.py`: encapsulates daily reset scheduling, invoked from `start_scheduler` / `stop_scheduler` in `src/app.py`.
  - `tray.py`: optional system tray integration; the launcher treats failures here as non-fatal (especially on Linux where GTK/AppIndicator may be missing).

`initialize_data_manager()` in `src/app.py` is the only supported way to initialize persistence and related services; it:
- Resolves the user data directory and creates `data/` inside it.
- Verifies write permissions via a sentinel file.
- Constructs `SQLiteDataManager(data_dir=...)` with a connection pool.
- Creates `PINManager` and `UpdateManager`, wiring them into `AppContext` and kicking off auto-update checks and weekly backups.

### Persistence and data model

- `src/sqlite_data_manager.py`
  - Provides a thread-safe, connection-pooled wrapper around SQLite, with the database located under the configured `data_dir`.
  - Manages schema for users, tasks, notes, settings, sessions, and other supporting tables (planner v2, strike history, analytics-related tables, etc.).
  - Exposes both high-level per-user helpers (`create_task_for_user`, `load_tasks_for_user`, `save_tasks_for_user`, `load_settings_for_user`, etc.) and lower-level utilities (`pooled_connection()`, `get_pool_stats()`).
  - Implements defensive logging and backoff around connection pool timeouts and retries.

Route modules and background jobs should, where possible, use the per-user helpers instead of hard-coding SQL; test coverage in `tests/test_unit.py` exercises these helpers heavily.

### Routing layer

All request handlers live in `src/routes/` and are grouped by concern. The pattern is:

- Each module defines a `Blueprint` and an `init_*_routes(...)` function that accepts an `AppContext`, helper callables (e.g., `get_user_id`, `ensure_data_manager`, `sanitize_input`), and any other dependencies.
- `src/app.py` constructs those dependencies, calls each `init_*_routes`, then registers the resulting blueprint on the main Flask app.

Important modules:

- `src/routes/core_routes.py`
  - Root UI routes (`/`, `/companion`), static asset helpers (fonts, manifest, service worker, favicon).
  - Health endpoints (`/health`, `/api/health/detailed`) that depend on `_get_app_version` and the presence of an initialized `data_manager`.
  - `/api/changelog` (serves `config/changelog.txt`) and `/api/analytics` (delegates to `src.analytics_manager.get_analytics_counters`).
- `src/routes/task_routes.py`
  - Task CRUD and actions under `/api/tasks/*`, including schedule/unschedule endpoints and CSV/TXT import via `src.services.importer`.
  - Uses injected `sanitize_input` (which defers to `security_manager.sanitize_input`) and `validate_task_data`.

Other blueprints follow a similar pattern (`notes_routes.py`, `planner_routes.py`, `settings_routes.py`, `mobile_routes.py`, `monitoring_routes.py`, `backups_routes.py`, `updates_routes.py`, `github_update_routes.py`, `pin_routes.py`) and use the same injected `AppContext` and helpers rather than global state.

### Security, monitoring, and CSRF

- `src/security_manager.py`
  - Centralizes input sanitization (`sanitize_input`), rate limiting (`check_rate_limit` with per-IP sliding windows and cleanup), and in-memory session secret tracking.
  - Maintains internal counters and exposes `get_rate_limit_stats()` for monitoring.
  - **This is explicitly called out as a no-touch area in `docs/AI_AGENT_GUIDELINES.md` except under direct human instruction.**
- `src/app.py`
  - Defines `require_csrf` as a decorator, but its implementation is currently a no-op that simply calls the wrapped function; past iterations tied this into `security_manager` and TTL-based CSRF tracking.
  - Defines `rate_limit` decorator that wraps handlers, enforces `security_manager.check_rate_limit`, and records request/exception events via `src.monitoring.monitor`.
- `src/monitoring.py` and the `PerformanceMonitor` tests in `tests/test_unit.py`
  - Provide metrics collection and export, including `/api/monitoring/export` (see `monitoring_routes.py`) which writes JSON under the user data directory.

Changes to CSRF, auth, or low-level security logic must respect the constraints summarized below.

## Agent-specific constraints (from docs/AI_AGENT_GUIDELINES.md)

Future Warp agents working in this repo must treat `docs/AI_AGENT_GUIDELINES.md` as authoritative. The most important points:

1. **Absolute no-touch areas (unless a human explicitly asks and understands the risk):**
   - `src/security_manager.py` and any CSRF-related decorators/helpers (e.g., `require_csrf` in `src/app.py`) and code using `security_manager` for CSRF/rate limiting/input sanitization.
   - Deep security/auth flows or anything that would change how sessions are validated.

2. **Legacy / compatibility code:**
   - Do not delete or heavily refactor endpoints and helpers that appear legacy or lightly used (e.g., older planner endpoints in `src/app.py` or backwards-compat helpers in `SQLiteDataManager`), even if they seem unused. Old builds, installers, or external automation may still depend on them.

3. **Generally safe change areas (small, behavior-preserving edits only):**
   - Frontend wiring and theme handling in `assets/static/js/*` and `assets/static/css/*` when aligning names with backend validation, or delegating loader behavior to the canonical implementations in `assets/static/js/app/app.js`.
   - Task import and task APIs in `src/routes/task_routes.py` when fixing clearly incorrect call signatures or wiring (e.g., argument ordering into `save_tasks` that contradicts its documentation and test expectations).
   - Test harness updates (`tests/run_tests.py`, new tests in `tests/test_*.py`) that do not alter runtime behavior.
   - Logging and metrics export paths, when the goal is to centralize under the user data directory via `get_user_data_dir()`.

4. **Version helpers and reuse:**
   - Prefer `_get_app_version()` in `src/app.py` over re-reading `config/version.json` manually in new endpoints. It is safe to replace duplicated version-reading code with calls to this helper as long as error handling remains equivalent.

5. **Decision rule:**
   - If a proposed change touches CSRF, `security_manager`, auth/session flows, or obviously legacy code, **stop and request explicit human guidance** instead of editing.
   - When in doubt, prefer writing notes or TODOs and linking to `docs/AI_AGENT_GUIDELINES.md` rather than making invasive changes.

## Documentation to consult

When making non-trivial changes, consult these repo documents first:

- `README.md` — canonical build and run instructions for Windows/Linux/macOS plus recent work summary (v15.2).
- `BUILD_INSTRUCTIONS.md` — detailed version auto-increment and Windows installer wiring based on `config/version.json` and `scripts/build.py`.
- `docs/BUILD-LINUX.md` — end-to-end `.deb` packaging flow using `fpm` and Linux-specific requirements.
- `docs/WINDOWS-TEST-GUIDE.md` — practical Windows dev/test walkthrough and WSL guidance.
- `docs/WSL-SETUP-GUIDE.md` — step-by-step WSL + Python + fpm setup to build `.deb` packages from Windows.
- `docs/AI_AGENT_GUIDELINES.md` — required reading for any AI/agent modifications, especially around security and legacy behavior.

Use these documents as the source of truth for build/test flows and high-impact behavior; keep `WARP.md` aligned with them when they change.