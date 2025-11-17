# Config Module Fix - Import Error Resolution

## Problem
The application failed to start with error:
```
ImportError: No module named 'src.core.config'
```

**Root Cause:** 
- `src/app.py` line 37 imported `from src.core.config import config`
- The `src/core/config.py` module file was missing
- Application tried to pass `config` object to templates (line 1091) but it couldn't be imported

## Solution

### 1. Created `src/core/config.py`
New configuration module with:
- **AppConfig class** - Main configuration container
  - Loads application name, version, debug mode, environment
  - Handles both development and PyInstaller frozen executable modes
  - Provides helper methods for asset and config paths
  
- **Global config instance** - Exported as `config` object
  - Initializes once at module load time
  - Available throughout application

### 2. Fixed `src/core/__init__.py`
Updated imports to match the actual class name:
```python
# Before (incorrect):
from .config import config, Config

# After (correct):
from .config import config, AppConfig
```

## Key Features of AppConfig

### Properties
- `app_name` - Application name ("Shakshuka")
- `app_version` - Version from `config/version.json` (default: "1.0.0")
- `debug_mode` - From DEBUG environment variable (default: False)
- `environment` - From ENVIRONMENT variable (default: "production")
- `app_root` - Root directory (auto-detected for both dev and frozen modes)

### Methods
- `get_asset_path(asset_type, filename)` - Get full path to assets
- `get_config_path(filename)` - Get full path to config files
- `to_dict()` - Convert to dictionary for template rendering

### Example Usage
```python
from src.core.config import config

# Access properties
print(config.app_version)      # "6.1.2"
print(config.app_name)          # "Shakshuka"
print(config.environment)       # "production"

# Use helper methods
icon_path = config.get_asset_path('images', 'icon.ico')
version_path = config.get_config_path('version.json')

# Pass to templates
render_template('index.html', config=config)
```

## Testing Verification

✅ **Verified:** Config module imports successfully
```
✓ Config loaded successfully
  App Name: Shakshuka
  Version: 6.1.2
```

## Files Modified/Created

| File | Action | Status |
|------|--------|--------|
| `src/core/config.py` | Created | ✅ New file |
| `src/core/__init__.py` | Updated | ✅ Fixed imports |
| `src/app.py` | Unchanged | ✅ Works with fix |

## Backward Compatibility

✅ All changes are backward compatible:
- `config` object maintains same interface
- Export in `__init__.py` is now correct
- No breaking changes to existing code

## Environment Variables Supported

- `DEBUG` - Set to "true" to enable debug mode (default: false)
- `ENVIRONMENT` - Set deployment environment (default: "production")

---

Generated: 2025-11-06
