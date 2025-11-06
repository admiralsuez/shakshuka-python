# Code Refactoring Plan - Shakshuka

**Status:** Planning Phase  
**Priority:** High  
**Complexity:** Medium  

---

## Executive Summary

The current `src/app.py` file has grown to 2000+ lines, mixing concerns and creating maintenance challenges. This plan breaks down the application into modular, testable components while preserving all functionality.

**Target:** Reduce `src/app.py` to ~500 lines (core Flask setup only)

---

## Issues to Address

### 1. ❌ Large File (2000+ lines)
**Problem:** Single file handles everything - routes, validation, scheduling, security
**Solution:** Modularize into focused services

### 2. ❌ Mixed Concerns
**Problem:** Database, validation, scheduling all in one file
**Solution:** Separate into service modules

### 3. ❌ Repeated Path Logic
**Problem:** Getting root directory happens 5+ times
**Solution:** Centralize in `src/utils/paths.py`

### 4. ❌ Deprecated Code
**Problem:** Old auth decorators, backward compatibility cruft
**Solution:** Remove unused code

### 5. ❌ Global State
**Problem:** Heavy reliance on `app_context` singleton
**Solution:** Improve but keep (thread-safe, works well for Flask)

---

## Proposed New Structure

```
src/
├── app.py (CORE - ~500 lines)
│   └── Flask setup, initialization, global config
├── routes/
│   ├── __init__.py
│   ├── tasks.py (200 lines) - Task CRUD endpoints
│   ├── auth.py (150 lines) - PIN auth endpoints
│   ├── updates.py (200 lines) - Update/GitHub endpoints
│   ├── health.py (50 lines) - Health check endpoints
│   └── planner.py (100 lines) - Planner endpoints (if needed)
├── services/
│   ├── __init__.py
│   ├── scheduler.py (150 lines) - Daily reset, scheduling
│   ├── validators.py (100 lines) - Input validation
│   ├── security.py (100 lines) - Security utilities
│   └── import_tasks.py (100 lines) - CSV/TXT parsing
├── utils/
│   ├── __init__.py
│   ├── paths.py (50 lines) - Path resolution (CENTRALIZED)
│   └── helpers.py (100 lines) - Common helpers
├── core/
│   ├── app_context.py (existing - 150 lines)
│   ├── launcher.py (existing)
│   └── config.py (existing)
└── __init__.py
```

---

## Detailed Module Breakdown

### 1. `src/utils/paths.py` - CENTRALIZED PATH LOGIC

**Purpose:** All path resolution in one place

```python
# Current duplicated logic (5+ times in app.py):
if getattr(sys, 'frozen', False):
    root_dir = os.path.dirname(sys.executable)
else:
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```

**Solution:**
```python
# src/utils/paths.py
def get_root_dir():
    """Get app root directory in dev or frozen mode"""
    
def get_static_dir():
    """Get static assets directory"""
    
def get_template_dir():
    """Get templates directory"""
    
def get_user_data_dir():
    """Get user data directory (AppData/Roaming)"""
    
def get_config_dir():
    """Get config directory"""
```

**Benefits:**
- Single source of truth
- Easy to maintain
- Testable
- Remove 100+ lines from app.py

---

### 2. `src/services/validators.py` - INPUT VALIDATION

**Current:** Lines 562-632 in app.py

**Extracted functions:**
- `validate_task_data()`
- `sanitize_input()`
- `validate_reset_time()`
- `parse_csv_tasks()`
- `parse_txt_tasks()`

**Benefits:**
- 70+ lines removed from app.py
- Validators testable independently
- Reusable across modules

---

### 3. `src/services/scheduler.py` - SCHEDULING LOGIC

**Current:** Lines 859-1010 in app.py

**Extracted functions:**
- `reset_daily_strikes_job()`
- `setup_daily_reset()`
- `check_and_run_missed_reset()`
- `scheduler_worker()`
- `start_scheduler()`

**Benefits:**
- 150+ lines removed
- Scheduling logic isolated
- Testable without Flask
- Easy to extend

---

### 4. `src/routes/tasks.py` - TASK ENDPOINTS

**Current:** Task-related routes scattered in app.py

**Endpoints:**
- `GET /api/tasks`
- `POST /api/tasks`
- `PUT /api/tasks/<id>`
- `DELETE /api/tasks/<id>`
- `POST /api/tasks/<id>/strike`
- `POST /api/tasks/<id>/complete`
- `POST /api/tasks/<id>/undo-strike`
- `POST /api/tasks/<id>/schedule`
- `POST /api/tasks/<id>/unschedule`
- `POST /api/tasks/import`

**Implementation:**
```python
# src/routes/tasks.py
from flask import Blueprint

tasks_bp = Blueprint('tasks', __name__, url_prefix='/api/tasks')

@tasks_bp.route('', methods=['GET'])
def get_tasks():
    # moved from app.py
    
@tasks_bp.route('', methods=['POST'])
def create_task():
    # moved from app.py
    
# ... etc
```

**In app.py:**
```python
from src.routes.tasks import tasks_bp
app.register_blueprint(tasks_bp)
```

**Benefits:**
- 300+ lines removed from app.py
- Routes organized logically
- Easy to test
- Scales well

---

### 5. `src/routes/auth.py` - PIN AUTHENTICATION

**Current:** Lines 1456-1606 in app.py

**Endpoints:**
- `GET /api/pin/status`
- `POST /api/pin/setup`
- `POST /api/pin/verify`
- `POST /api/pin/reset`
- `POST /api/pin/logout`
- `GET /api/account`
- `GET /login`

**Benefits:**
- 150+ lines removed
- Auth logic isolated
- Easier to add new auth methods

---

### 6. `src/routes/updates.py` - UPDATE ENDPOINTS

**Current:** Lines 1144-1420 in app.py

**Endpoints:**
- `GET /api/check-updates`
- `POST /api/updates/check`
- `POST /api/github/check-update`
- `POST /api/github/download-update`
- `GET /api/changelog`

**Benefits:**
- 276+ lines removed
- Update logic isolated
- Easy to modify

---

### 7. `src/routes/health.py` - HEALTH ENDPOINTS

**Current:** Lines 393-449 in app.py

**Endpoints:**
- `GET /health`
- `GET /api/health/detailed`

**Benefits:**
- Organized and grouped

---

## Implementation Sequence

### Phase 1: Utilities (Low Risk)
1. Create `src/utils/paths.py` - Extract path logic
2. Create `src/utils/helpers.py` - Extract helpers
3. Update imports in `app.py`

**Estimated time:** 1-2 hours  
**Risk:** Low (no functional changes)

### Phase 2: Services (Medium Risk)
1. Create `src/services/validators.py`
2. Create `src/services/scheduler.py`
3. Update imports in `app.py`
4. Test validators and scheduler

**Estimated time:** 2-3 hours  
**Risk:** Medium (need to test validators)

### Phase 3: Routes (Medium Risk)
1. Create `src/routes/tasks.py`
2. Create `src/routes/auth.py`
3. Create `src/routes/updates.py`
4. Create `src/routes/health.py`
5. Register blueprints in `app.py`
6. Full integration testing

**Estimated time:** 3-4 hours  
**Risk:** Medium-High (major refactoring)

### Phase 4: Cleanup (Low Risk)
1. Remove deprecated code
2. Clean up app_context (documentation only)
3. Final testing

**Estimated time:** 1 hour  
**Risk:** Low

### Phase 5: Documentation (Low Risk)
1. Document new module structure
2. Create migration guide
3. Update README

**Estimated time:** 1-2 hours  
**Risk:** Low

---

## Backward Compatibility

✅ **No Breaking Changes:**
- All endpoints remain the same
- All functionality preserved
- Only internal organization changes
- No API changes
- No database schema changes

---

## Testing Strategy

### Unit Tests (Post-Refactor)
- Test validators independently
- Test scheduler logic independently
- Test security utilities

### Integration Tests
- Test all endpoints
- Test database operations
- Test auto-save
- Test daily reset

### Regression Testing
- Ensure all original features work
- Manual testing of key flows

---

## Benefits After Refactoring

| Aspect | Before | After |
|--------|--------|-------|
| Main app.py lines | 2000+ | ~500 |
| Modules | 1 | 10+ |
| Path resolution duplication | 5+ places | 1 place |
| Testability | Hard | Easy |
| Maintainability | Low | High |
| Code reuse | Limited | Good |
| Onboarding time | ~2 hours | ~30 mins |

---

## Files to Create

1. ✅ `src/utils/paths.py` - 50 lines
2. ✅ `src/utils/helpers.py` - 100 lines
3. ✅ `src/services/__init__.py` - 5 lines
4. ✅ `src/services/validators.py` - 100 lines
5. ✅ `src/services/scheduler.py` - 150 lines
6. ✅ `src/services/security.py` - 100 lines
7. ✅ `src/services/import_tasks.py` - 100 lines
8. ✅ `src/routes/__init__.py` - 5 lines
9. ✅ `src/routes/tasks.py` - 200 lines
10. ✅ `src/routes/auth.py` - 150 lines
11. ✅ `src/routes/updates.py` - 200 lines
12. ✅ `src/routes/health.py` - 50 lines

**Total lines to move:** ~1200 lines  
**Main app.py reduction:** ~70-80%

---

## Risk Assessment

| Phase | Risk | Mitigation |
|-------|------|-----------|
| Utilities | Low | No functional changes |
| Services | Medium | Comprehensive unit tests |
| Routes | High | Full regression testing |
| Cleanup | Low | Keep deprecated code available |
| Documentation | Low | None needed |

---

## Timeline

- **Phase 1 (Utilities):** Day 1 - 1-2 hours
- **Phase 2 (Services):** Day 2 - 2-3 hours
- **Phase 3 (Routes):** Day 2-3 - 3-4 hours
- **Phase 4 (Cleanup):** Day 3 - 1 hour
- **Phase 5 (Docs):** Day 3 - 1-2 hours

**Total:** ~1-2 days with full testing

---

## Deliverables

1. ✅ Modularized codebase
2. ✅ Updated imports in all files
3. ✅ Full integration tests passing
4. ✅ Documentation of new structure
5. ✅ README with module overview

---

## Future Improvements

After refactoring, consider:
1. Add more unit tests (70%+ coverage)
2. Add type hints (mypy compatibility)
3. Consider async/await for long operations
4. Database query optimization
5. Caching layer for frequently accessed data

---

## Next Steps

1. ✅ Approve refactoring plan
2. ⏳ Create utility modules
3. ⏳ Create service modules
4. ⏳ Create route blueprints
5. ⏳ Full testing
6. ⏳ Merge and deploy
