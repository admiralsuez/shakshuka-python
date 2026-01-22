# Dead Code Analysis

## JavaScript Dead Code

### `assets/static/js/utils/utils.js`

#### Functions to Remove (Unused)
1. **`getCSRFToken()`** - CSRF not used in current auth flow (PIN-based)
   - Only exported in Utils, never called
   - Can be removed safely

2. **`animateElement(element, keyframes, options)`** - DOM animation helper
   - Not called anywhere in codebase
   - Can be removed

3. **`getQueryParams()`** - URL query parameter parser
   - Not called anywhere in codebase
   - Can be removed

4. **`setQueryParams(params)`** - URL query parameter setter
   - Not called anywhere in codebase
   - Can be removed

5. **`readFileAsText(file)`** - File reader helper
   - Not called anywhere in codebase
   - Can be removed

6. **`readFileAsDataURL(file)`** - File reader helper
   - Not called anywhere in codebase
   - Can be removed

#### Functions to Keep (Used)
1. **`makeAuthenticatedRequest()`** - Still used in:
   - `app/schedule-modal.js` (2 calls)
   - `app/app.js` (4 calls: exportData, clearData, loadSettingsLegacy, loadAccountSettings)
   - `app/account.js` (2 calls)
   - **Action**: Migrate these to use `apiCall` or `apiRequestJson`, then remove

2. **`showLoading(element, text)`** - Still used in:
   - `app/loading-overlay.js` (redefined locally)
   - `app/import-tasks.js` (2 calls)
   - `app/app.js` (4 calls: exportData, clearData, loadAppData)
   - **Action**: Keep or migrate to centralized loading state management

3. **`hideLoading(element, originalText)`** - Still used in:
   - `app/app.js` (4 calls: exportData, clearData)
   - **Action**: Keep or migrate to centralized loading state management

4. **`downloadFile(data, filename, type)`** - Still used in:
   - `app/app.js` (1 call: exportData)
   - **Action**: Keep (useful utility)

### Migration Plan for `makeAuthenticatedRequest()`

**Files to update**:
1. `app/schedule-modal.js`: Replace with `apiCall` or `apiRequestJson`
2. `app/app.js`: Replace with `apiCall` or `apiRequestJson`
3. `app/account.js`: Replace with `apiCall` or `apiRequestJson`

**After migration**: Remove `makeAuthenticatedRequest()` from `utils.js`

## Python Dead Code

### Potential Dead Functions (Need Usage Analysis)

#### `src/utils/helpers.py`
- `clamp(value, min_value, max_value)` - Check if used
- `chunks(lst, n)` - Check if used
- `dict_from_keys(keys, value)` - Check if used
- `sanitize_dict_for_json(d)` - Check if used

#### `src/utils/sanitizers.py`
- `sanitize_sql_input(value)` - Should use parameterized queries instead
- `strip_tags(text)` - Check if used

#### `src/services/tray.py`
- `get_last_tray_error()` - Check if used
- `_set_last_tray_error(message)` - Internal helper

## Naming Convention Issues

### JavaScript (Should be camelCase)
✅ Most JS functions already follow camelCase
- Exception: Some internal helpers use `_snake_case` (acceptable for private functions)

### Python (Should be snake_case)
✅ All Python functions already follow snake_case

### API Endpoints (Should be kebab-case or snake_case)
✅ All endpoints follow consistent pattern: `/api/resource` or `/api/resource/action`

## Utility Alignment Issues

### Missing JS Equivalents of Python Utils
1. **Validators** (`src/utils/validators.py`):
   - `validate_task_data()` - No JS equivalent (server-side only)
   - `validate_time_format()` - No JS equivalent (could add)
   - `validate_email()` - JS has `isValidEmail()` ✅
   - `validate_username()` - No JS equivalent
   - `validate_password()` - No JS equivalent

2. **Sanitizers** (`src/utils/sanitizers.py`):
   - `sanitize_input()` - No JS equivalent
   - `sanitize_string()` - JS has `sanitizeHTML()` ✅
   - `sanitize_filename()` - No JS equivalent
   - `sanitize_html_content()` - No JS equivalent

3. **Paths** (`src/utils/paths.py`):
   - All path helpers are server-side only (not needed in JS)

4. **Helpers** (`src/utils/helpers.py`):
   - `get_app_version()` - No JS equivalent (could add)
   - `is_newer_version()` - No JS equivalent (could add)
   - `parse_version_string()` - No JS equivalent
   - `format_version()` - No JS equivalent
   - `safe_get_nested()` - No JS equivalent (could add)
   - `merge_dicts()` - No JS equivalent (could add)

### Missing Python Equivalents of JS Utils
1. **DOM Helpers** (JS-only, not applicable to Python):
   - `isElementVisible()`, `getElementPosition()`, `scrollToElement()`, etc.

2. **Browser APIs** (JS-only, not applicable to Python):
   - `copyToClipboard()`, `downloadFile()`, `readFileAsText()`, etc.

## Recommendations

### Immediate Actions
1. **Remove unused JS functions**:
   - `getCSRFToken()`
   - `animateElement()`
   - `getQueryParams()`
   - `setQueryParams()`
   - `readFileAsText()`
   - `readFileAsDataURL()`

2. **Migrate `makeAuthenticatedRequest()` usage**:
   - Update 8 call sites to use `apiCall` or `apiRequestJson`
   - Remove `makeAuthenticatedRequest()` after migration

3. **Audit Python utils**:
   - Check usage of `clamp()`, `chunks()`, `dict_from_keys()`, `sanitize_dict_for_json()`
   - Remove if unused

### Future Enhancements
1. **Add JS validators** (if needed client-side):
   - `validateTimeFormat(timeStr)` - mirror Python version
   - `validateUsername(username)` - mirror Python version
   - `validatePassword(password)` - mirror Python version

2. **Add JS helpers** (if needed):
   - `getAppVersion()` - fetch from `/api/version`
   - `isNewerVersion(newVer, currentVer)` - mirror Python version
   - `safeGetNested(obj, keys, default)` - mirror Python version
   - `mergeDicts(base, override)` - mirror Python version

3. **Standardize error handling**:
   - Ensure all JS API calls use consistent error objects
   - Ensure all Python routes return consistent error responses
   - Document error response format in API docs
