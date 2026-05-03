# Codebase Analysis - Outdated Logic Patterns

## Executive Summary
Found **7 major outdated patterns** similar to Android sync issues. Most are in polling/timer logic and sequential operations. **3 are critical**, **4 are moderate**.

---

## 🔴 CRITICAL ISSUES

### 1. **Update Progress Polling** (CRITICAL)
**File:** `assets/static/js/app/backup-update.js:419-488`
**Pattern:** Sequential polling with fixed 800ms interval

```javascript
updatePollInterval = setInterval(async () => {
    // Polls /api/updates/progress every 800ms
    // No exponential backoff
    // No max wait time
    // Continues indefinitely until status changes
}, 800);
```

**Problems:**
- Fixed 800ms interval = 75 requests/minute
- No exponential backoff (unlike Android fix)
- No max wait time - could poll forever
- Blocks UI during download

**Comparison to Android Fix:**
- Android: 5s → 7.5s → 11s → 30s (exponential)
- Desktop: 800ms constant (inefficient)

**Impact:** High CPU/network usage during updates

**Fix:** Use exponential backoff like Android approval poller

---

### 2. **Auto-Update Check Worker** (CRITICAL)
**File:** `src/update_manager.py:952-1020`
**Pattern:** Blocking while loop with polling

```python
while self.update_check_enabled:
    try:
        update_info = self.check_for_updates()
        
        if update_info and self.update_config.get("auto_install_enabled"):
            self.start_download(update_info)
            
            # Blocking polling loop
            max_wait_time = 600  # 10 minutes
            wait_interval = 2    # Check every 2 seconds
            waited = 0
            
            while waited < max_wait_time:
                status = self.get_download_status()
                if status['status'] == 'ready':
                    break
                time.sleep(wait_interval)  # ← Blocking
                waited += wait_interval
        
        time.sleep(sleep_time)  # Sleep for 24 hours
```

**Problems:**
- Blocks entire thread during download wait
- Fixed 2-second polling interval
- No exponential backoff
- 10-minute timeout is arbitrary
- Runs in daemon thread (can't be interrupted cleanly)

**Impact:** Thread starvation, can't cancel downloads gracefully

**Fix:** Use event-based notifications instead of polling

---

### 3. **Weekly Backup Worker** (CRITICAL)
**File:** `src/update_manager.py:1021-1055`
**Pattern:** Infinite blocking loop in daemon thread

```python
def backup_worker():
    while True:  # ← Infinite loop
        try:
            last_backup = self.update_config.get("last_weekly_backup")
            if last_backup:
                last_backup_time = datetime.fromisoformat(last_backup)
                if datetime.now() - last_backup_time < timedelta(days=7):
                    time.sleep(3600)  # Sleep 1 hour
                    continue
            
            backup_name = self.create_backup("weekly")
            time.sleep(24 * 3600)  # Sleep 24 hours
```

**Problems:**
- Infinite loop with no exit condition
- Daemon thread can't be stopped cleanly
- 24-hour sleep is wasteful
- No way to trigger backup on-demand
- If backup fails, waits 1 hour then retries (no backoff)

**Impact:** Can't gracefully shutdown, wasted resources

**Fix:** Use scheduler service (already exists!) instead of daemon threads

---

## 🟡 MODERATE ISSUES

### 4. **Mobile Inbox Polling** (MEDIUM)
**File:** `assets/static/js/app/mobile-inbox.js:579-584`
**Pattern:** Simple setInterval with no deduplication

```javascript
function startPolling() {
    if (pollingTimer) return;
    pollingTimer = window.setInterval(pollInboxOnce, 10000);  // Every 10 seconds
    pollInboxOnce();
}

async function pollInboxOnce() {
    if (pollingInFlight) return;  // Guard against concurrent polls
    pollingInFlight = true;
    
    try {
        const data = await fetchJson('/api/mobile/inbox/pending', { cacheTTL: 0 });
        // ... process ...
    } finally {
        pollingInFlight = false;
    }
}
```

**Problems:**
- Fixed 10-second interval (could be 5s with backoff)
- No exponential backoff
- No max wait time
- Polls even when page is hidden (has guard but still wasteful)

**Comparison to Android Fix:**
- Android: 5s → 7.5s → 11s → 30s (exponential)
- Desktop: 10s constant

**Impact:** Moderate - 6 requests/minute vs 2 with backoff

**Fix:** Add exponential backoff, max wait time

---

### 5. **Companion Sync Polling** (MEDIUM)
**File:** `assets/static/js/app/companion-sync.js:44-82`
**Pattern:** Fixed interval polling for sync request

```javascript
const SYNC_POLL_INTERVAL_MS = 5000;  // 5 seconds
const SYNC_POLL_MAX_TICKS = 18;      // 90 seconds max

function _startSyncRequestPoll() {
    _stopSyncRequestPoll();
    _syncRequestPollInterval = setInterval(_syncRequestPollTick, SYNC_POLL_INTERVAL_MS);
}

async function _syncRequestPollTick() {
    _syncRequestPollCount++;
    if (_syncRequestPollCount > SYNC_POLL_MAX_TICKS) {
        _stopSyncRequestPoll();
        return;
    }
    // Poll /api/mobile/inbox/pending
}
```

**Problems:**
- Fixed 5-second interval
- No exponential backoff
- Max 90 seconds is good, but could be smarter
- Polls even if page is hidden

**Comparison to Android Fix:**
- Android: 5s → 7.5s → 11s → 30s (exponential)
- Desktop: 5s constant

**Impact:** Moderate - 12 requests/90s vs 4-5 with backoff

**Fix:** Add exponential backoff like Android

---

### 6. **QR Code Auto-Refresh** (MEDIUM)
**File:** `assets/static/js/app/mobile-inbox.js:115-178`
**Pattern:** Single setTimeout for QR refresh

```javascript
async function refreshPairingCode() {
    // ... fetch new code ...
    
    const refreshDelay = Math.max((expiresIn - 30) * 1000, 30000);
    qrRefreshTimer = setTimeout(() => {
        const modal = getEl('pair-phone-modal');
        if (modal && (modal.classList.contains('active') || modal.style.display === 'flex')) {
            refreshPairingCode();  // ← Recursive call
        }
    }, refreshDelay);
}
```

**Problems:**
- Recursive setTimeout (creates new timer each time)
- No cleanup if modal closes during refresh
- If refresh fails, no retry logic
- Timer not cleared on modal close

**Impact:** Low - only affects pairing flow, but could leak timers

**Fix:** Clear timer on modal close, add error handling

---

### 7. **GitHub Update Progress Simulation** (MEDIUM)
**File:** `assets/static/js/app/backup-update.js:204-214`
**Pattern:** Fake progress with fixed interval

```javascript
let fakePct = 0;
let progressTimer = null;
if (progressDiv && progressFill && progressText) {
    progressTimer = setInterval(() => {
        if (fakePct < 95) {
            fakePct += 3;  // Increment by 3% every 500ms
            progressFill.style.width = Math.min(fakePct, 95) + '%';
            progressText.textContent = 'Downloading update...';
        }
    }, 500);  // Fixed 500ms interval
}
```

**Problems:**
- Fake progress is misleading
- Fixed 500ms interval
- No correlation with actual download progress
- Timer not always cleared on error

**Impact:** Low - UX issue, not functional

**Fix:** Use actual progress from `/api/updates/progress`

---

## 🔴 ADDITIONAL CRITICAL ISSUES (Database)

### 8. **Load-Modify-Save Pattern** (CRITICAL - N+1 equivalent)
**Files:** `task_routes.py:468-491, 494-625, 628-679`
**Pattern:** Load ALL tasks, find one, modify, save ALL

```python
# complete_task endpoint
tasks = data_manager.load_tasks_for_user(user_id)  # ← Load ALL tasks
for i, task in enumerate(tasks):
    if task['id'] == task_id:  # ← Find the one
        tasks[i]['completed'] = True  # ← Modify
        if data_manager.save_tasks_for_user(user_id, tasks):  # ← Save ALL
            return jsonify(tasks[i])

# Same pattern in strike_task (line 526-612)
# Same pattern in undo_strike (line 637-679)
```

**Problems:**
- Loads ALL tasks just to modify ONE
- If user has 500 tasks, loads 500 to update 1
- Saves ALL 500 tasks back to database
- Database has `update_task_for_user()` method but it's not used!
- This is N+1 equivalent: O(N) load + O(N) save for O(1) operation

**Impact:** CRITICAL
- 500 tasks = 500 items loaded/saved for single update
- Slow API response
- High memory usage
- Database contention

**Fix:** Use `update_task_for_user()` instead
```python
# Instead of:
tasks = data_manager.load_tasks_for_user(user_id)
for i, task in enumerate(tasks):
    if task['id'] == task_id:
        tasks[i]['completed'] = True
        data_manager.save_tasks_for_user(user_id, tasks)

# Use:
data_manager.update_task_for_user(user_id, task_id, {'completed': True})
```

---

### 9. **Redundant Database Queries in Update** (CRITICAL)
**File:** `sqlite_data_manager.py:2161-2173`
**Pattern:** Query same task twice

```python
def update_task_for_user(self, user_id, task_id, task_data):
    cursor = conn.execute(
        'SELECT id FROM tasks WHERE id = ? AND user_id = ?',
        (task_id, user_id),
    )
    if not cursor.fetchone():  # ← Query 1: Check if exists
        return False
    
    backup_cursor = conn.execute(
        'SELECT * FROM tasks WHERE id = ? AND user_id = ?',  # ← Query 2: Get full task
        (task_id, user_id)
    )
    backup_row = backup_cursor.fetchone()
```

**Problems:**
- Queries same task twice
- First query only checks existence
- Second query gets full data
- Could combine into one query

**Impact:** MEDIUM
- 2 database round-trips instead of 1
- Doubles query overhead

**Fix:** Combine into single query
```python
cursor = conn.execute('SELECT * FROM tasks WHERE id = ? AND user_id = ?', (task_id, user_id))
backup_row = cursor.fetchone()
if not backup_row:
    return False
```

---

### 10. **Inefficient Task Save** (CRITICAL)
**File:** `sqlite_data_manager.py:1897-1942`
**Pattern:** Load all, delete all, insert all

```python
def save_tasks_for_user(self, user_id, tasks):
    # Load existing tasks for backup
    cursor = conn.execute('SELECT * FROM tasks WHERE user_id = ?', (user_id,))
    for row in cursor.fetchall():  # ← Load ALL
        backup_tasks.append(self._row_to_task_dict(row))
    
    conn.execute('DELETE FROM tasks WHERE user_id = ?', (user_id,))  # ← Delete ALL
    
    task_rows = [self._task_dict_to_row(task, user_id) for task in tasks_normalized]
    conn.executemany('''INSERT INTO tasks...''', task_rows)  # ← Insert ALL
```

**Problems:**
- Loads all tasks for backup (expensive)
- Deletes all tasks
- Inserts all tasks
- This is a full table replacement for every save!
- Should use UPDATE for existing, INSERT for new

**Impact:** CRITICAL
- 500 tasks = DELETE 500 + INSERT 500 for every save
- Slow performance
- High database load
- Inefficient for small changes

**Fix:** Use UPSERT pattern
```python
# Instead of DELETE + INSERT ALL:
for task in tasks:
    conn.execute('''
        INSERT OR REPLACE INTO tasks (id, user_id, ...) VALUES (...)
    ''', task_row)
```

---

## Summary Table

| Issue | File | Type | Severity | Pattern | Impact |
|-------|------|------|----------|---------|--------|
| Update progress polling | backup-update.js | JS | 🔴 CRITICAL | Fixed interval | 75 req/min |
| Auto-update worker | update_manager.py | Python | 🔴 CRITICAL | Blocking loop | Thread starvation |
| Weekly backup worker | update_manager.py | Python | 🔴 CRITICAL | Daemon thread | Can't stop |
| Load-modify-save | task_routes.py | Python | 🔴 CRITICAL | N+1 pattern | O(N) for O(1) op |
| Redundant queries | sqlite_data_manager.py | Python | 🔴 CRITICAL | Duplicate query | 2x queries |
| Inefficient save | sqlite_data_manager.py | Python | 🔴 CRITICAL | DELETE+INSERT ALL | O(N) for any change |
| Mobile inbox polling | mobile-inbox.js | JS | 🟡 MEDIUM | Fixed interval | 6 req/min |
| Companion sync polling | companion-sync.js | JS | 🟡 MEDIUM | Fixed interval | 12 req/90s |
| QR code refresh | mobile-inbox.js | JS | 🟡 MEDIUM | Recursive timer | Timer leaks |
| GitHub progress sim | backup-update.js | JS | 🟡 MEDIUM | Fake progress | Misleading UX |

---

## Recommended Fixes (Priority Order)

### 🔥 Phase 1: CRITICAL Database Issues (Highest Impact)

1. **Fix Load-Modify-Save Pattern** (`task_routes.py`)
   - Replace 3 endpoints: `complete_task`, `strike_task`, `undo_strike`
   - Use `update_task_for_user()` instead of load-all/save-all
   - **Impact:** 500 tasks = 500→1 items loaded/saved
   - **Estimated speedup:** 10-50x faster for users with many tasks

2. **Fix Inefficient Task Save** (`sqlite_data_manager.py:1897-1942`)
   - Replace DELETE+INSERT ALL with UPSERT pattern
   - Use `INSERT OR REPLACE` for each task
   - **Impact:** Eliminates full table replacement on every save
   - **Estimated speedup:** 5-10x faster saves

3. **Fix Redundant Database Queries** (`sqlite_data_manager.py:2161-2173`)
   - Combine two SELECT queries into one
   - Check existence and get data in single query
   - **Impact:** 2x fewer database round-trips
   - **Estimated speedup:** 2x faster updates

### Phase 2: Critical (Backend Threading)
4. **Replace daemon threads with scheduler service**
   - Move `_auto_update_check_worker` to scheduler
   - Move `backup_worker` to scheduler
   - Use existing `scheduler_service` (already in codebase!)
   - **Impact:** Graceful shutdown, proper resource cleanup

### Phase 3: Critical (Frontend Polling)
5. **Add exponential backoff to update polling**
   - Use same pattern as Android approval poller
   - 800ms → 1.2s → 1.8s → 2.7s → 4s (max)
   - **Impact:** 75 req/min → 15 req/min (80% reduction)

### Phase 4: Moderate (Frontend)
6. **Add exponential backoff to inbox/sync polling**
   - Mobile inbox: 10s → 15s → 22s → 30s
   - Companion sync: 5s → 7.5s → 11s → 16s → 30s
   - **Impact:** 6 req/min → 2 req/min

7. **Fix QR code timer cleanup**
   - Clear timer on modal close
   - Add error handling
   - **Impact:** Prevent timer leaks

8. **Use real progress data**
   - Remove fake progress simulation
   - Display actual `/api/updates/progress` values
   - **Impact:** Better UX

---

## Code Reuse Opportunity

The Android approval poller we just built can be adapted for:
- Update progress polling
- Mobile inbox polling
- Companion sync polling
- QR code refresh

All follow the same pattern:
1. Register item for polling
2. Single polling loop checks all items
3. Exponential backoff per item
4. Max wait time per item
5. Auto-cleanup when done

---

## Scheduler Service Already Exists!

Found in codebase: `src/services/scheduler.py`

Instead of daemon threads, use:
```python
scheduler_service.schedule_job(
    'weekly_backup',
    job_func=self.create_backup,
    trigger='cron',
    day_of_week='sun',
    hour=2,  # 2 AM
    minute=0
)
```

This is **much cleaner** than daemon threads and integrates with existing system.

---

## Testing Recommendations

1. **Update polling:** Monitor network requests during update
2. **Backup worker:** Verify it runs weekly, not constantly
3. **Inbox polling:** Check request frequency over 5 minutes
4. **Sync polling:** Verify exponential backoff in browser console
5. **QR refresh:** Close modal during refresh, verify no timer leaks

