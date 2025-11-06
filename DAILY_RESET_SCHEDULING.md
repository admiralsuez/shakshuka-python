# Daily Reset Scheduling Behavior

## Overview
When the daily reset occurs (at your configured reset time, default 8:00 AM), the system now clears ALL scheduled tasks from the planner, with intelligent handling based on task completion status.

---

## Reset Behavior

### 1. Tasks Struck TODAY (Not Completed)
**Action:** Clear strike flag AND remove from schedule
- Strike flag: `struck_today = false`
- Schedule cleared: `scheduled_date`, `scheduled_hour`, `scheduled_minute`, `scheduled_duration` all set to `null`
- **Result:** Task returns to "Available Tasks" pool, ready to be rescheduled

**Example:**
```
Before Reset:
- Title: "Review Report"
- struck_today: true
- completed: false
- scheduled_date: "2025-11-06"
- scheduled_hour: 14
- scheduled_minute: 30

After Reset:
- Title: "Review Report"
- struck_today: false
- completed: false
- scheduled_date: null
- scheduled_hour: null
- scheduled_minute: null
↓ Task now appears in Available Tasks
```

---

### 2. Tasks Struck FOREVER (Completed)
**Action:** Clear strike flag but keep task hidden
- Strike flag: `struck_today = false`
- Completed status: `completed = true` (unchanged)
- Schedule cleared: (already not scheduled)
- **Result:** Task remains hidden from available tasks

**Example:**
```
Before Reset:
- Title: "Finish Project"
- struck_today: true
- completed: true
- scheduled_date: null

After Reset:
- Title: "Finish Project"
- struck_today: false
- completed: true
- scheduled_date: null
↓ Task remains completed, hidden from planner
```

---

### 3. Regular Scheduled Tasks (Not Struck)
**Action:** Clear all scheduling
- All scheduled tasks from ANY day get unscheduled
- Only tasks that are NOT completed are affected
- **Result:** Planner is clean, tasks return to available pool

**Example:**
```
Before Reset:
- Title: "Prepare Presentation"
- struck_today: false
- completed: false
- scheduled_date: "2025-11-06"
- scheduled_hour: 10
- scheduled_minute: 0

After Reset:
- Title: "Prepare Presentation"
- struck_today: false
- completed: false
- scheduled_date: null
- scheduled_hour: null
- scheduled_minute: null
↓ Task returns to Available Tasks
```

---

## When Does Reset Occur?

1. **Daily at scheduled time** (default 8:00 AM)
   - Set in Settings → Daily Reset Time
   - Uses local time zone

2. **On app startup** (if missed)
   - Checks if reset time has passed
   - If yes and tasks are struck, runs immediately

3. **Every 15 minutes** (background check)
   - Catches resets missed due to sleep/hibernation
   - Runs quietly without user notification

---

## Data State Changes

### Strike Flags
| Property | Before | After | Condition |
|----------|--------|-------|-----------|
| `struck_today` | true | false | All struck tasks |
| `struck_date` | Date | null | All struck tasks |
| `strike_report` | Text | null | All struck tasks |
| `completed` | varies | varies | Unchanged |

### Scheduling Data
| Property | Before | After | Condition |
|----------|--------|-------|-----------|
| `scheduled_date` | Date/null | null | All scheduled non-completed tasks |
| `scheduled_hour` | 0-23 | null | All scheduled non-completed tasks |
| `scheduled_minute` | 0-59 | null | All scheduled non-completed tasks |
| `scheduled_duration` | Minutes | null | All scheduled non-completed tasks |

---

## Available Tasks Display Logic

After reset, tasks appear in "Available Tasks" if:
- ✅ `completed = false` (not struck forever)
- ✅ `struck_today = false` (not struck for today, or already reset)
- ✅ `scheduled_date = null` (not scheduled)

Tasks are HIDDEN if:
- ❌ `completed = true` (struck forever/completed)
- ❌ `struck_forever = true` (marked as completed)

---

## Logging

The reset process logs detailed information:

```
[INFO] Starting daily strikes reset job
[DEBUG] Task 'Review Report' unscheduled after today's strike reset
[DEBUG] Task 'Prepare Presentation' unscheduled during daily reset
[INFO] Daily reset done: 2 strikes cleared, 1 tasks unscheduled
```

---

## User Experience Flow

### Scenario 1: Struck a Task Today
1. **10:30 AM:** User strikes "Review Report" for today
2. **8:00 AM Next Day:** Reset occurs
   - Strike flag cleared
   - Task unscheduled
3. **8:01 AM:** User sees "Review Report" back in Available Tasks
   - Ready to schedule or strike again

### Scenario 2: Completed a Task (Strike Forever)
1. **2:00 PM:** User strikes "Final Project" forever
2. **8:00 AM Next Day:** Reset occurs
   - Strike flag cleared
   - Task remains completed/hidden
3. **8:01 AM:** User doesn't see "Final Project" in available tasks
   - Task remains in completed history

### Scenario 3: Scheduled Tasks Accumulate
1. **Various times:** User schedules multiple tasks for today
2. **8:00 AM Next Day:** Reset occurs
   - All scheduled tasks unscheduled
3. **8:01 AM:** All tasks back in Available Tasks
   - Clean planner, ready for new schedule

---

## Configuration

**To change reset time:**
1. Go to Settings → Daily Reset Time
2. Select desired time (e.g., 8:00 AM, 6:00 PM)
3. Reset reschedules automatically

**Current reset time is stored in:**
- Settings database
- Default: 08:00 (8:00 AM local time)

---

## Technical Implementation

**File:** `src/app.py`
**Function:** `reset_daily_strikes_job()`

**Key Logic:**
```python
# For struck-today tasks
if task.get('struck_today'):
    is_struck_forever = task.get('completed', False)
    task['struck_today'] = False
    
    # Only unschedule if not completed
    if not is_struck_forever:
        clear_all_scheduling_fields()

# For all other scheduled tasks
if has_schedule and not is_completed:
    clear_all_scheduling_fields()
```

---

## Examples

### Example 1: Mixed Task States Before Reset

```
Task 1: "Email Review"
- struck_today: true
- completed: false
- scheduled_date: "2025-11-06", hour: 14

Task 2: "Finish Report"
- struck_today: true
- completed: true
- scheduled_date: null

Task 3: "Prepare Slides"
- struck_today: false
- completed: false
- scheduled_date: "2025-11-06", hour: 16

Task 4: "Code Review"
- struck_today: false
- completed: false
- scheduled_date: null
```

### After Reset at 8:00 AM Next Day

```
Task 1: "Email Review"
- struck_today: false ✅
- completed: false
- scheduled_date: null ✅
↓ Appears in Available Tasks

Task 2: "Finish Report"
- struck_today: false
- completed: true
↓ Remains hidden (completed)

Task 3: "Prepare Slides"
- struck_today: false
- completed: false
- scheduled_date: null ✅
↓ Appears in Available Tasks

Task 4: "Code Review"
- struck_today: false
- completed: false
- scheduled_date: null
↓ Remains in Available Tasks
```

---

## FAQ

**Q: Will my scheduled tasks be lost?**
A: No, only the scheduling information is cleared. Tasks are preserved. You can reschedule them anytime.

**Q: What if I don't want tasks unscheduled at reset?**
A: Current design clears all scheduling at reset for a fresh daily planner. This can be customized in future versions.

**Q: What about tasks scheduled for future days?**
A: Currently, only same-day scheduling is used. Future dates are not supported in the current planner.

**Q: Do I need to change any settings?**
A: No, reset works automatically. Just set your preferred reset time in Settings.

---

## Related Features

- **Daily Reset Time:** Set in Settings → Daily Reset Time
- **Available Tasks:** Shows all active, unscheduled, non-completed tasks
- **Planner V2:** Uses available tasks for scheduling
- **Strike Functionality:** Strike Today vs Strike Forever
