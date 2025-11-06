# Shakshuka Feature Requirements Analysis

**Date:** 2025-11-06  
**Analysis of:** 5 Feature Requirements

---

## Issue 1: Timezone Handling in Reset Time ✅ PARTIALLY WORKING

### Expected Behavior
User sets custom time in settings to reset, and it should follow the user's timezone.

### Current Implementation (src/app.py)
- **Lines 889-922:** `check_and_run_missed_reset()` uses `datetime.now()` (local time)
- **Lines 924-951:** `setup_daily_reset()` validates reset time and schedules using `schedule.every().day.at(reset_time_str).do()`
- **Lines 953-1010:** `reset_daily_strikes_job()` uses `datetime.now()` (local time)
- **Lines 1027-1040:** `get_timezone_aware_time()` function exists but is NOT USED

### Issues Found
✅ **CORRECT:** Uses `datetime.now()` (local time) instead of `datetime.utcnow()` - this respects local timezone  
✅ **CORRECT:** Settings load `timezone` field (line 2271, 2283)  
⚠️ **ISSUE:** `get_timezone_aware_time()` function (lines 1027-1040) is NEVER CALLED  
⚠️ **ISSUE:** No actual timezone conversion - code assumes server timezone = user timezone  
⚠️ **ISSUE:** Missing `pytz` dependency handling for proper timezone support

### Log Evidence
```
2025-11-06 14:44:45,883 - src.app - INFO - Daily reset scheduled for 02:44
2025-11-06 14:44:45,881 - src.sqlite_data_manager - Successfully loaded 4 tasks
```
Scheduler is working but no timezone conversion visible in logs.

### Status
**PARTIALLY WORKING** - Uses local time but doesn't support user-selected timezones


---

## Issue 2: Scheduled Tasks Removal on Reset ✅ WORKING

### Expected Behavior
When reset time happens, all scheduled tasks in daily planner should be removed (striked or not).

### Current Implementation (src/app.py)
- **Lines 2218-2226:** In `reset_daily_strikes()` endpoint:
```python
# Unschedule previous-day tasks that aren't completed
for i, t in enumerate(tasks):
    sd = t.get('scheduled_date')
    if sd and sd < today_local:
        tasks[i]['scheduled_hour'] = None
        tasks[i]['scheduled_minute'] = None
        tasks[i]['scheduled_date'] = None
        tasks[i]['scheduled_duration'] = None
        unscheduled += 1
```

- **Lines 987-996:** In `reset_daily_strikes_job()` (background job):
```python
# Unschedule previous-day tasks that aren't completed
unscheduled = 0
for t in tasks:
    sd = t.get('scheduled_date')
    if sd and sd < today_str_local:
        t['scheduled_hour'] = None
        t['scheduled_minute'] = None
        t['scheduled_date'] = None
        t['scheduled_duration'] = None
        unscheduled += 1
```

### Log Evidence
```
2025-11-06 14:44:00,080 - src.sqlite_data_manager - Successfully saved 4 tasks
2025-11-06 14:44:00,082 - werkzeug - POST /api/tasks/reset-daily-strikes HTTP/1.1" 200
2025-11-06 14:44:00,101 - src.app - Daily reset: no changes needed
```

### Status
✅ **WORKING** - Code correctly clears ALL scheduled tasks (hour, minute, date, duration)

---

## Issue 3: New Task View Switching ❌ NOT WORKING

### Expected Behavior
When new task is entered, it should:
1. Add to active view
2. Auto-switch to active view (if not already there)

### Current Implementation (assets/static/js/tasks.js)
- **Lines 58-88:** `saveTask()` function:
```javascript
async function saveTask() {
    const taskData = getTaskFormData();
    if (!taskData) return;
    
    try {
        const response = await apiCall('/api/tasks', {
            method: 'POST',
            body: JSON.stringify(taskData)
        });
        
        if (response.ok) {
            closeTaskModal();
            loadTasks();  // <-- Just reloads all tasks
            // If we're on the planner page, refresh available tasks immediately
            try {
                if (AppState.get && AppState.get('currentPage') === 'planner') {
                    if (window.DailyPlannerV2 && typeof window.DailyPlannerV2.loadAvailableTasks === 'function') {
                        window.DailyPlannerV2.loadAvailableTasks();
                    }
                }
            } catch (e) { /* no-op */ }
            Utils.safeShowNotification('Task saved successfully!', 'success');
        }
    }
}
```

- **Lines 90-118:** `saveQuickTask()` - same issue

### Issues Found
❌ **NOT SWITCHING VIEWS:** After saving task, calls `loadTasks()` but does NOT switch to 'active' filter  
❌ **NO FILTER SET:** Code doesn't call `setActiveFilter('active')`  
❌ **USER STAYS IN COMPLETED VIEW:** If user was viewing "completed" tasks, new task won't be visible there

### Missing Code
```javascript
// Should add after loadTasks():
setActiveFilter('active');  // Switch to active view
```

### Status
❌ **NOT WORKING** - New tasks don't trigger view switch to active


---

## Issue 4: Completed View Empty State ❌ NOT WORKING

### Expected Behavior
After deleting task from completed view:
1. Stay in completed view
2. Show empty state if no more completed tasks

### Current Implementation (assets/static/js/tasks.js)
- **Lines 140-175:** `deleteTask()` function:
```javascript
async function deleteTask(taskId) {
    if (!confirm('Are you sure you want to delete this task?')) return;
    
    try {
        const response = await apiCall(`/api/tasks/${taskId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            loadTasks();  // <-- Just reloads without preserving filter
            // Refresh other components...
            Utils.safeShowNotification('Task deleted successfully!', 'success');
        }
    }
}
```

- **Lines 320-349:** `renderTasks()` uses `AppState.get('currentFilter')` but doesn't preserve it

### Issues Found
❌ **NOT PRESERVING VIEW:** `deleteTask()` calls `loadTasks()` which reloads from API  
❌ **LIKELY SWITCHES VIEWS:** If completed view becomes empty, renderTasks shows "No tasks found" message  
⚠️ **FILTER STATE LOST:** After delete, currentFilter might reset to 'active'

### What's Happening in Logs
```
2025-11-06 14:51:25,601 - src.app - API delete_task called for task ed26de0b-f188-49fb-a75c-022eac663c10
2025-11-06 14:51:25,609 - src.app - Successfully deleted task
2025-11-06 14:51:25,610 - werkzeug - DELETE /api/tasks/... HTTP/1.1" 200
```

No indication that view/filter state is preserved.

### Status
❌ **NOT WORKING** - Likely switches to different view after deletion


---

## Issue 5: Expired Empty State Message ❌ NOT IMPLEMENTED

### Expected Behavior
When expired view is empty, display: "Yay no tasks that have were missed"

### Current Implementation (assets/static/js/tasks.js)
- **Lines 331-340:** Generic empty state for ALL views:
```javascript
if (filteredTasks.length === 0) {
    tasksContainer.innerHTML = `
        <div class="no-tasks">
            <i class="fas fa-clipboard-list"></i>
            <h3>No tasks found</h3>
            <p>Add some tasks to get started!</p>
        </div>
    `;
    return;
}
```

### Issues Found
❌ **GENERIC MESSAGE:** Same "No tasks found" message for ALL filter types  
❌ **NO CONDITIONAL LOGIC:** Doesn't check if filter === 'expired'  
❌ **MISSING CUSTOM MESSAGE:** No code path for "Yay no tasks that have were missed"

### Task Filtering Logic (lines 419-442)
```javascript
function filterTasks(tasks, filter) {
    // ... filter == 'expired' returns overdue tasks
    case 'overdue':
        return tasks.filter(task => {
            if (task.due_date) {
                const dueDate = new Date(task.due_date);
                return dueDate < today && !task.struck_forever;
            }
            return false;
        });
}
```

Filter logic exists, but empty state message is not customized.

### Status
❌ **NOT IMPLEMENTED** - Generic message used for all views


---

## Summary Table

| Issue | Feature | Status | Severity | Location |
|-------|---------|--------|----------|----------|
| 1 | Timezone handling | ⚠️ Partial | Medium | `src/app.py` lines 889-951 |
| 2 | Scheduled task removal | ✅ Working | N/A | `src/app.py` lines 2218-2226 |
| 3 | New task view switching | ❌ Not Working | High | `assets/static/js/tasks.js` lines 58-88 |
| 4 | Completed view empty state | ❌ Not Working | High | `assets/static/js/tasks.js` lines 140-175 |
| 5 | Expired empty message | ❌ Not Implemented | Low | `assets/static/js/tasks.js` lines 331-340 |

---

## Recommended Fixes (Priority Order)

### HIGH PRIORITY
1. **Issue 3:** Add `setActiveFilter('active')` after task creation
2. **Issue 4:** Preserve filter state after deletion
3. **Issue 5:** Add conditional empty state messages

### MEDIUM PRIORITY  
4. **Issue 1:** Implement proper timezone support with pytz

### WORKING
- Issue 2: No action needed
