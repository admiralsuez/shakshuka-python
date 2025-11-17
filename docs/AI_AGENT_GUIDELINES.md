# AI Agent Guidelines for Shakshuka

This document explains **what future AI coding agents should and should not touch** in this codebase, and why. It is intended to prevent accidental breakage of security-sensitive or fragile areas.

---

## 1. Absolute No‑Touch Zones

These are areas that **must not be modified unless a human explicitly requests it and understands the risks**.

### 1.1 CSRF and Security Manager

**Files / modules (non-exhaustive):**

- `src/security_manager.py`
- Any CSRF decorators or helpers (e.g. `require_csrf` in `src/app.py`)
- Any code using `security_manager` for CSRF, rate limiting, or input sanitization

**Rationale:**

- CSRF and security logic are tightly coupled to frontend expectations and the existing session model.
- The user has explicitly stated that **touching CSRF can break the entire app**.
- Security changes require coordinated updates across backend, frontend, installers, and possibly external documentation.

**Guideline:**

- Do **not** rename, remove, or change CSRF-related functions, decorators, or their call sites.
- Do **not** change how `security_manager` is instantiated or used.
- If a bug appears to involve CSRF or `security_manager`, stop and ask for explicit human instructions before editing.

### 1.2 Likely-unused or ambiguous backend code

There are areas of the backend that may be legacy or rarely used (e.g. old planner v1 endpoints, legacy auth stubs). Future agents should **not assume these can be deleted or changed**, even if they look unused.

Examples:

- Legacy planner endpoints in `src/app.py` (e.g. `/api/planner/schedule` v1).
- Legacy password-based auth code in the backend, if present.
- Backwards-compat methods in `SQLiteDataManager` (e.g. `load_tasks`, `save_tasks` wrappers).

**Rationale:**

- Some tooling, old builds, or external automation may still depend on these endpoints or functions.
- Deleting or silently changing them can break user workflows that are not obvious from the current UI.

**Guideline:**

- Do **not** delete or significantly refactor anything that looks legacy/compat unless the user explicitly confirms it is safe.
- Small, clearly safe additions (e.g. adding a new allowed theme string) are acceptable, but altering control flow or removing functions is not.

---

## 2. Changes That Are Generally Safe

The following areas are relatively safe to modify, as long as changes are small, localized, and behaviour-preserving.

### 2.1 Frontend UI and theme wiring

**Files:**

- `assets/static/js/features/settings.js`
- `assets/static/css/*.css`
- `assets/templates/index.html`

**Safe patterns:**

- Fixing obvious wiring bugs (e.g. frontend reading `settings.autostart` when the backend actually returns `autostart_enabled`).
- Adding theme names to backend validation **only if those themes are already supported in CSS and the settings UI**.
- Adjusting the loader logic in `app-init.js` to delegate to the canonical implementations in `app.js` without changing the underlying loader behaviour.

**Example of a safe change already made:**

- `Settings.load()` now reads `settings.autostart_enabled` (with a fallback to the old `settings.autostart`) so the Windows autostart toggle reflects the real backend state.
- `SQLiteDataManager._validate_settings()` now allows `depression` and `focus` themes, which are already defined in CSS.

### 2.2 Task import, task API, and planner v2

**Files:**

- `src/routes/task_routes.py`
- `src/sqlite_data_manager.py`

**Safe patterns:**

- Fixing argument order where the called function’s signature is known and clearly misused.
- Using the `*_for_user` methods (`load_tasks_for_user`, `save_tasks_for_user`, etc.) consistently, without changing their internal logic.

**Example of a safe change already made:**

- In `import_tasks()`, `save_tasks` is now called as `save_tasks(existing_tasks, user_id)` instead of `save_tasks(user_id, existing_tasks)`, matching the documented signature and preventing validation failures.

### 2.3 Test runner and tooling

**Files:**

- `tests/run_tests.py`
- Build / test helper scripts

**Safe patterns:**

- Updating deprecated or removed APIs in the test harness (e.g. replacing `unittest.makeSuite` with `unittest.defaultTestLoader.loadTestsFromTestCase`).
- Adding or adjusting test utilities that do not alter runtime application behaviour.

**Example of a safe change already made:**

- `tests/run_tests.py` now uses `unittest.defaultTestLoader` instead of `unittest.makeSuite`, so the test suite can run on modern Python.

### 2.4 Logging, metrics, and export locations

**Files:**

- `src/app.py` (`/api/monitoring/export`, `/api/analytics`, etc.)
- `src/sqlite_data_manager.py` (logging improvements)

**Safe patterns:**

- Redirecting file outputs from relative `data/` paths to the centralized user data directory via `get_user_data_dir()`, to avoid permission issues.
- Adding or downgrading log statements where it does not change control flow.

**Example of a safe change already made:**

- `/api/monitoring/export` now writes metrics exports under `get_user_data_dir()/metrics/…` instead of a bare `data/` directory.

---

## 3. Version handling and duplication

**Helper:**

- `_get_app_version()` in `src/app.py` (reads `config/version.json` safely in dev and frozen modes).

**Guideline:**

- Prefer `_get_app_version()` over re-implementing version.json reading in multiple endpoints.
- It is safe to replace duplicated version-reading blocks with `_get_app_version()` as long as you keep the same error handling behaviour.

**Example of a safe change already made:**

- The `/` route and update-check endpoints (`/api/check-updates`, `/api/updates/check`, `/api/github/check-update`) now call `_get_app_version()` instead of duplicating file I/O.

---

## 4. Loader and initialization

**Files:**

- `assets/static/js/app.js` (canonical loader logic, including minimum duration and animated task list)
- `assets/static/js/core/app-init.js` (wires Auth, Utils, Keyboard, and loader together)

**Guideline:**

- Treat `app.js` as the **source of truth** for loader behaviour.
- `app-init.js` should only delegate to the global `showLoadingScreen` / `hideLoadingScreen` if they exist.

**Example of a safe change already made:**

- `app-init.js` no longer has its own fallback fade logic; it simply calls `window.showLoadingScreen()` / `window.hideLoadingScreen()` when available. This avoids divergence between two different loader implementations.

---

## 5. Error handling

**File:**

- `assets/static/js/utils-new/error-handler.js`

**Guideline:**

- Error handler initialization must **never** crash just because `Utils.Logger` is not available yet.
- It is safe to:
  - Guard `Utils.Logger` access with `if (typeof Utils !== 'undefined' && Utils.Logger) { … }`.
  - Fall back to `console.error` / `console.info` when logging utilities are not loaded.

**Example of a safe change already made:**

- `ErrorHandler.init()` now checks for `Utils.Logger` and falls back to `console.info('Error handlers initialized')` if it isn’t present.

---

## 6. How to decide if a change is “safe enough”

When considering any modification, future AI agents should ask:

1. **Does this touch CSRF, security_manager, or auth flows?**
   - If yes: **stop** and request explicit human approval.

2. **Is this code clearly used by the current UI or tests?**
   - If no (it looks legacy/unused), **do not remove or refactor**, unless the user explicitly says it is safe.

3. **Is the change behaviour-preserving and minimal?**
   - Examples: fixing argument order, adding a missing theme that already exists in CSS, or delegating to an existing function.

4. **Can the change be verified with tests or manual checks?**
   - Prefer changes where you can re-run `tests/run_tests.py` or manually reason about the effect.

If the answer to any of these questions is uncertain, prefer to **leave the code as is** and document the concern instead of editing.

---

## 7. Summary for future agents

- **Never touch CSRF or security_manager without explicit human instruction.**
- **Avoid deleting or heavily refactoring legacy / likely-unused backend code.**
- Focus on **small, targeted fixes** where the intent is clear and the behaviour can be reasoned about (UI wiring, argument order, test harness, logging, version helper reuse).
- When in doubt, **write documentation or comments instead of code changes**, and ask the user for confirmation.
