# Optimization TODO List

## 🔥 PHASE 1: CRITICAL DATABASE FIXES (Do First - Highest Impact)

### Task 1.1: Fix Load-Modify-Save Pattern in complete_task
**File:** `src/routes/task_routes.py:468-491`
**Severity:** 🔴 CRITICAL
**Estimated Impact:** 10-50x speedup for users with 500+ tasks
**Time:** 15 minutes

**Current Code:**
```python
@task_bp.route('/<task_id>/complete', methods=['POST'])
def complete_task(task_id):
    user_id = _get_user_id()
    data_manager = _get_data_manager()
    
    tasks = data_manager.load_tasks_for_user(user_id)  # ← Load ALL
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            tasks[i]['completed'] = True
            tasks[i]['completed_at'] = datetime.now().isoformat()
            if data_manager.save_tasks_for_user(user_id, tasks):  # ← Save ALL
                return jsonify(tasks[i])
    
    return jsonify({'error': 'Task not found'}), 404
```

**Fix:**
```python
@task_bp.route('/<task_id>/complete', methods=['POST'])
def complete_task(task_id):
    user_id = _get_user_id()
    data_manager = _get_data_manager()
    
    # Use direct update instead of load-all/save-all
    success = data_manager.update_task_for_user(
        user_id, 
        task_id, 
        {
            'completed': True,
            'completed_at': datetime.now().isoformat(),
            'status': TaskStatus.COMPLETED.value
        }
    )
    
    if success:
        updated_task = data_manager.get_task_by_id(user_id, task_id)
        if updated_task:
            return jsonify(updated_task)
    
    return jsonify({'error': 'Task not found'}), 404
```

**Checklist:**
- [ ] Replace `complete_task` endpoint
- [ ] Test with 1 task
- [ ] Test with 500 tasks
- [ ] Verify response time improvement
- [ ] Check analytics counter still increments

---

### Task 1.2: Fix Load-Modify-Save Pattern in strike_task
**File:** `src/routes/task_routes.py:494-625`
**Severity:** 🔴 CRITICAL
**Estimated Impact:** 10-50x speedup
**Time:** 30 minutes

**Current Code:**
```python
@task_bp.route('/<task_id>/strike', methods=['POST'])
def strike_task(task_id):
    user_id = _get_user_id()
    strike_data = request.json or {}
    strike_type = strike_data.get('type')
    
    data_manager = _get_data_manager()
    tasks = data_manager.load_tasks_for_user(user_id)  # ← Load ALL
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            # ... modify task ...
            if data_manager.save_tasks_for_user(user_id, tasks):  # ← Save ALL
                return jsonify(tasks[i])
    
    return jsonify({'error': 'Task not found'}), 404
```

**Fix:**
```python
@task_bp.route('/<task_id>/strike', methods=['POST'])
def strike_task(task_id):
    user_id = _get_user_id()
    strike_data = request.json or {}
    strike_type = strike_data.get('type')
    report = strike_data.get('report', '')
    
    # Validate input
    if not strike_type or strike_type not in ['today', 'forever']:
        return jsonify({'error': 'Invalid strike type'}), 400
    
    data_manager = _get_data_manager()
    
    # Get task once
    task = data_manager.get_task_by_id(user_id, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    today = datetime.now().strftime('%Y-%m-%d')
    updates = {}
    
    if strike_type == 'today':
        daily_strikes = task.get('daily_strikes', {})
        strikes_today = daily_strikes.get(today, 0)
        
        if strikes_today >= 2:
            return jsonify({'error': 'Maximum strikes reached for today'}), 400
        
        strike_number = strikes_today + 1
        daily_strikes[today] = strike_number
        
        updates = {
            'daily_strikes': daily_strikes,
            'struck_today': True,
            'struck_date': today,
            'strike_report': report,
            'strike_count': task.get('strike_count', 0) + 1
        }
        
        # Compute recurrence snooze
        try:
            recurrence_type = (task.get('recurrence_type') or '').strip().lower()
            recurrence_param = task.get('recurrence_param')
            next_date = None
            
            if recurrence_type == 'every_n_days':
                try:
                    n = int(recurrence_param or 0)
                except Exception:
                    n = 0
                if n and n > 1:
                    base_dt = datetime.strptime(today, '%Y-%m-%d')
                    next_date = base_dt + timedelta(days=n)
            elif recurrence_type == 'weekly':
                try:
                    target_wd = int(recurrence_param)
                except Exception:
                    target_wd = None
                if target_wd is not None and 0 <= target_wd <= 6:
                    base_dt = datetime.strptime(today, '%Y-%m-%d')
                    days_ahead = (target_wd - base_dt.weekday()) % 7
                    if days_ahead == 0:
                        days_ahead = 7
                    next_date = base_dt + timedelta(days=days_ahead)
            
            if next_date is not None:
                updates['snoozed_until'] = next_date.strftime('%Y-%m-%d')
        except Exception:
            logger.exception("Failed to compute recurrence snooze for task %s", task_id)
        
        # Record event
        try:
            data_manager.add_strike_today_report_event(
                user_id=user_id,
                task_id=task_id,
                day=today,
                strike_number=strike_number,
                report=report,
            )
        except Exception:
            logger.exception("Failed to add strike_today report event")
    
    elif strike_type == 'forever':
        updates = {
            'completed': True,
            'completed_at': datetime.now().isoformat(),
            'struck_forever': True,
            'struck_today': True,
            'struck_date': today,
            'strike_report': report,
            'strike_count': task.get('strike_count', 0) + 1,
            'status': TaskStatus.COMPLETED.value
        }
    
    # Record strike event
    try:
        data_manager.add_strike_event(
            user_id=user_id,
            task_id=task_id,
            day=today,
            strike_type=strike_type,
        )
    except Exception:
        logger.exception("Failed to add strike event")
    
    # Single update instead of load-all/save-all
    success = data_manager.update_task_for_user(user_id, task_id, updates)
    
    if success:
        updated_task = data_manager.get_task_by_id(user_id, task_id)
        if updated_task:
            # Increment analytics
            try:
                from src.analytics_manager import increment_strike_counter
                increment_strike_counter()
            except Exception:
                logger.exception("Failed to increment strike counter")
            
            return jsonify(updated_task)
    
    return jsonify({'error': 'Failed to strike task'}), 500
```

**Checklist:**
- [ ] Replace `strike_task` endpoint
- [ ] Test strike today (multiple times)
- [ ] Test strike forever
- [ ] Test recurrence snooze calculation
- [ ] Verify analytics counter increments
- [ ] Test with 500 tasks

---

### Task 1.3: Fix Load-Modify-Save Pattern in undo_strike
**File:** `src/routes/task_routes.py:628-679`
**Severity:** 🔴 CRITICAL
**Estimated Impact:** 10-50x speedup
**Time:** 20 minutes

**Current Code:**
```python
@task_bp.route('/<task_id>/undo-strike', methods=['POST'])
def undo_strike(task_id):
    user_id = _get_user_id()
    data_manager = _get_data_manager()
    
    tasks = data_manager.load_tasks_for_user(user_id)  # ← Load ALL
    
    for i, task in enumerate(tasks):
        if task['id'] == task_id:
            if task.get('struck_today'):
                # ... modify task ...
                if data_manager.save_tasks_for_user(user_id, tasks):  # ← Save ALL
                    return jsonify(tasks[i])
    
    return jsonify({'error': 'Task not found'}), 404
```

**Fix:**
```python
@task_bp.route('/<task_id>/undo-strike', methods=['POST'])
def undo_strike(task_id):
    user_id = _get_user_id()
    data_manager = _get_data_manager()
    
    # Get task once
    task = data_manager.get_task_by_id(user_id, task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    
    if not task.get('struck_today'):
        return jsonify({'error': 'Task is not struck for today'}), 400
    
    today = datetime.now().strftime('%Y-%m-%d')
    was_completed = task.get('completed', False)
    
    updates = {}
    
    if was_completed:
        # Undo strike forever
        updates = {
            'completed': False,
            'completed_at': None,
            'struck_forever': False,
            'struck_today': False,
            'struck_date': None,
            'strike_report': None,
            'strike_count': max(0, task.get('strike_count', 0) - 1),
            'status': TaskStatus.PENDING.value
        }
    else:
        # Undo regular strike today
        daily_strikes = task.get('daily_strikes', {})
        strikes_today = daily_strikes.get(today, 0)
        
        if strikes_today > 0:
            daily_strikes[today] = strikes_today - 1
        
        updates = {
            'daily_strikes': daily_strikes,
            'struck_today': False if daily_strikes.get(today, 0) == 0 else True,
            'struck_date': None if daily_strikes.get(today, 0) == 0 else today,
            'strike_report': None if daily_strikes.get(today, 0) == 0 else task.get('strike_report'),
            'strike_count': max(0, task.get('strike_count', 0) - 1)
        }
    
    # Single update instead of load-all/save-all
    success = data_manager.update_task_for_user(user_id, task_id, updates)
    
    if success:
        updated_task = data_manager.get_task_by_id(user_id, task_id)
        if updated_task:
            return jsonify(updated_task)
    
    return jsonify({'error': 'Failed to undo strike'}), 500
```

**Checklist:**
- [ ] Replace `undo_strike` endpoint
- [ ] Test undo strike today
- [ ] Test undo strike forever
- [ ] Test with 500 tasks
- [ ] Verify strike_count decrements correctly

---

### Task 1.4: Fix Redundant Database Queries in update_task_for_user
**File:** `src/sqlite_data_manager.py:2161-2173`
**Severity:** 🔴 CRITICAL
**Estimated Impact:** 2x faster updates
**Time:** 10 minutes

**Current Code:**
```python
def update_task_for_user(self, user_id, task_id, task_data):
    # Query 1: Check if exists
    cursor = conn.execute(
        'SELECT id FROM tasks WHERE id = ? AND user_id = ?',
        (task_id, user_id),
    )
    if not cursor.fetchone():
        return False
    
    # Query 2: Get full task
    backup_cursor = conn.execute(
        'SELECT * FROM tasks WHERE id = ? AND user_id = ?',
        (task_id, user_id)
    )
    backup_row = backup_cursor.fetchone()
```

**Fix:**
```python
def update_task_for_user(self, user_id, task_id, task_data):
    # Single query: Get full task and check existence
    cursor = conn.execute(
        'SELECT * FROM tasks WHERE id = ? AND user_id = ?',
        (task_id, user_id)
    )
    backup_row = cursor.fetchone()
    
    if not backup_row:
        return False
```

**Checklist:**
- [ ] Replace query logic
- [ ] Test update still works
- [ ] Verify backup still created
- [ ] Check performance improvement

---

### Task 1.5: Fix Inefficient Task Save (DELETE+INSERT ALL)
**File:** `src/sqlite_data_manager.py:1897-1942`
**Severity:** 🔴 CRITICAL
**Estimated Impact:** 5-10x faster saves
**Time:** 30 minutes

**Current Code:**
```python
def save_tasks_for_user(self, user_id, tasks):
    # Load all for backup
    cursor = conn.execute('SELECT * FROM tasks WHERE user_id = ?', (user_id,))
    for row in cursor.fetchall():
        backup_tasks.append(self._row_to_task_dict(row))
    
    # Delete all
    conn.execute('DELETE FROM tasks WHERE user_id = ?', (user_id,))
    
    # Insert all
    task_rows = [self._task_dict_to_row(task, user_id) for task in tasks_normalized]
    conn.executemany('''INSERT INTO tasks...''', task_rows)
```

**Fix:**
```python
def save_tasks_for_user(self, user_id, tasks):
    max_retries = 3
    retry_delay = 0.1
    
    for attempt in range(max_retries):
        try:
            with self._lock:
                tasks_normalized = [self._normalize_task_dict(t) for t in (tasks or [])]
                
                if not self._validate_tasks(tasks_normalized):
                    self.logger.error(f"Task validation failed for user {user_id}")
                    return False
                
                self._ensure_user_exists(user_id)
                
                with self._get_connection() as conn:
                    conn.execute('BEGIN IMMEDIATE TRANSACTION')
                    
                    try:
                        # Use UPSERT instead of DELETE+INSERT
                        for task in tasks_normalized:
                            task_row = self._task_dict_to_row(task, user_id)
                            conn.execute('''
                                INSERT OR REPLACE INTO tasks (
                                    id, user_id, title, description, project, owner, priority, status,
                                    completed, completed_at, due_date, estimated_duration, scheduled_hour,
                                    scheduled_minute, scheduled_date, scheduled_duration, struck_forever, struck_today, struck_date, strike_report, strike_count,
                                    daily_strikes, refreshed_at, recurrence_type, recurrence_param, snoozed_until, subtasks, created_at, updated_at
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ''', task_row)
                        
                        # Verify count matches
                        count_cursor = conn.execute('SELECT COUNT(*) FROM tasks WHERE user_id = ?', (user_id,))
                        inserted_count = count_cursor.fetchone()[0]
                        
                        if inserted_count != len(tasks_normalized):
                            raise Exception(f"Count mismatch: expected {len(tasks_normalized)}, got {inserted_count}")
                        
                        conn.commit()
                        self.logger.info(f"Successfully saved {len(tasks_normalized)} tasks for user {user_id}")
                        return True
                    
                    except Exception as inner_e:
                        conn.rollback()
                        self.logger.error(f"Transaction failed for user {user_id}, attempt {attempt + 1}: {inner_e}")
                        raise
        
        except Exception as e:
            self.logger.error(f"Error saving tasks for user {user_id}, attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay * (2 ** attempt))
                continue
            return False
    
    return False
```

**Checklist:**
- [ ] Replace save logic with UPSERT
- [ ] Test save with new tasks
- [ ] Test save with updated tasks
- [ ] Test save with deleted tasks (removed from list)
- [ ] Verify count verification still works
- [ ] Test with 500 tasks

---

## 🔴 PHASE 2: CRITICAL THREADING FIXES

### Task 2.1: Replace Auto-Update Worker with Scheduler
**File:** `src/update_manager.py:952-1020`
**Severity:** 🔴 CRITICAL
**Time:** 45 minutes

**Current Code:**
```python
def _auto_update_check_worker(self):
    """Background worker for automatic update checking and installation"""
    while self.update_check_enabled:  # ← Infinite loop
        try:
            update_info = self.check_for_updates()
            
            if update_info:
                if self.update_config.get("auto_install_enabled", False):
                    self.start_download(update_info)
                    
                    # Blocking polling
                    max_wait_time = 600
                    wait_interval = 2
                    waited = 0
                    
                    while waited < max_wait_time:  # ← Blocking loop
                        status = self.get_download_status()
                        if status['status'] == 'ready':
                            break
                        time.sleep(wait_interval)  # ← Blocks thread
                        waited += wait_interval
            
            time.sleep(sleep_time)  # ← Sleep 24 hours
```

**Fix:**
```python
# In __init__ or setup method:
def _setup_auto_update_scheduler(self):
    """Setup auto-update checking with scheduler instead of daemon thread"""
    from src.services.scheduler import scheduler_service
    
    check_interval_hours = self.update_config.get("check_interval_hours", 24)
    
    # Schedule update check every N hours
    scheduler_service.schedule_job(
        'auto_update_check',
        job_func=self._check_and_install_update,
        trigger='interval',
        hours=check_interval_hours,
        replace_existing=True
    )
    
    self.logger.info(f"Auto-update check scheduled every {check_interval_hours} hours")

def _check_and_install_update(self):
    """Check for updates and install if auto-install enabled"""
    try:
        update_info = self.check_for_updates()
        
        if not update_info:
            self.logger.debug("No updates available")
            return
        
        self.logger.info(f"Update available: {update_info['version']}")
        
        if not self.update_config.get("auto_install_enabled", False):
            self.logger.info("Auto-install disabled, skipping")
            return
        
        # Start download in background (non-blocking)
        self.start_download(update_info)
        self.logger.info(f"Download started for version {update_info['version']}")
        
        # Don't wait for download - let it complete asynchronously
        # The download status endpoint will handle progress
        
    except Exception as e:
        self.logger.exception("Error in auto-update check: %s", e)

# Remove the old _auto_update_check_worker method entirely
```

**Checklist:**
- [ ] Add `_setup_auto_update_scheduler()` method
- [ ] Add `_check_and_install_update()` method
- [ ] Call `_setup_auto_update_scheduler()` in `__init__`
- [ ] Remove old `_auto_update_check_worker()` method
- [ ] Remove daemon thread creation for auto-update
- [ ] Test scheduler triggers correctly
- [ ] Verify graceful shutdown works

---

### Task 2.2: Replace Weekly Backup Worker with Scheduler
**File:** `src/update_manager.py:1021-1055`
**Severity:** 🔴 CRITICAL
**Time:** 30 minutes

**Current Code:**
```python
def schedule_weekly_backup(self):
    """Schedule weekly automatic backups"""
    def backup_worker():
        while True:  # ← Infinite loop
            try:
                last_backup = self.update_config.get("last_weekly_backup")
                if last_backup:
                    last_backup_time = datetime.fromisoformat(last_backup)
                    if datetime.now() - last_backup_time < timedelta(days=7):
                        time.sleep(3600)  # ← Sleep 1 hour
                        continue
                
                backup_name = self.create_backup("weekly")
                self.update_config["last_weekly_backup"] = datetime.now().isoformat()
                self._save_update_config(self.update_config)
                self.logger.info("Weekly backup created successfully: %s", backup_name)
                
                time.sleep(24 * 3600)  # ← Sleep 24 hours
```

**Fix:**
```python
def _setup_weekly_backup_scheduler(self):
    """Setup weekly backup with scheduler instead of daemon thread"""
    from src.services.scheduler import scheduler_service
    
    # Schedule backup every Sunday at 2 AM
    scheduler_service.schedule_job(
        'weekly_backup',
        job_func=self._perform_weekly_backup,
        trigger='cron',
        day_of_week='sun',
        hour=2,
        minute=0,
        replace_existing=True
    )
    
    self.logger.info("Weekly backup scheduled for Sundays at 2:00 AM")

def _perform_weekly_backup(self):
    """Perform weekly backup"""
    try:
        backup_name = self.create_backup("weekly")
        self.update_config["last_weekly_backup"] = datetime.now().isoformat()
        self.update_config["last_weekly_backup_name"] = backup_name
        self._save_update_config(self.update_config)
        self.logger.info("Weekly backup created successfully: %s", backup_name)
    except Exception as e:
        self.logger.exception("Error in weekly backup: %s", e)

# Remove the old schedule_weekly_backup method entirely
```

**Checklist:**
- [ ] Add `_setup_weekly_backup_scheduler()` method
- [ ] Add `_perform_weekly_backup()` method
- [ ] Call `_setup_weekly_backup_scheduler()` in `__init__`
- [ ] Remove old `schedule_weekly_backup()` method
- [ ] Remove daemon thread creation
- [ ] Test scheduler triggers on Sunday at 2 AM
- [ ] Verify graceful shutdown works

---

## 🟡 PHASE 3: FRONTEND POLLING FIXES

### Task 3.1: Add Exponential Backoff to Update Progress Polling
**File:** `assets/static/js/app/backup-update.js:419-488`
**Severity:** 🔴 CRITICAL
**Estimated Impact:** 80% reduction in requests (75 → 15 req/min)
**Time:** 20 minutes

**Current Code:**
```javascript
updatePollInterval = setInterval(async () => {
    // Polls every 800ms = 75 requests/minute
    try {
        const res = await fetch('/api/updates/progress');
        // ... handle response ...
    } catch (e) {
        // ... error handling ...
    }
}, 800);  // ← Fixed 800ms interval
```

**Fix:**
```javascript
class UpdateProgressPoller {
    constructor() {
        this.pollingTimer = null;
        this.isPolling = false;
        this.pollInterval = 800;  // Start at 800ms
        this.nextCheckTime = Date.now();
        this.maxInterval = 4000;  // Max 4 seconds
        this.maxWaitTime = 600000;  // 10 minutes
        this.startTime = Date.now();
    }
    
    start() {
        if (this.pollingTimer) return;
        
        this.pollingTimer = setInterval(() => {
            this.checkProgress();
        }, 100);  // Check every 100ms if it's time
    }
    
    async checkProgress() {
        const now = Date.now();
        
        // Skip if not time yet
        if (now < this.nextCheckTime) return;
        
        // Skip if already polling
        if (this.isPolling) return;
        
        // Give up if exceeded max wait time
        if (now - this.startTime > this.maxWaitTime) {
            this.stop();
            return;
        }
        
        this.isPolling = true;
        
        try {
            const res = await fetch('/api/updates/progress');
            if (!res.ok) throw new Error(`HTTP ${res.status}`);
            
            const status = await res.json();
            const st = (status.status || '').toLowerCase();
            
            if (st === 'downloading') {
                const pct = Math.max(0, Math.min(100, status.progress || 0));
                const progressFill = document.getElementById('progress-fill');
                const progressText = document.getElementById('progress-text');
                
                if (progressFill) progressFill.style.width = pct + '%';
                if (progressText) {
                    const downloadedMB = ((status.downloaded || 0) / (1024 * 1024)).toFixed(1);
                    const totalMB = status.total ? ((status.total) / (1024 * 1024)).toFixed(1) : '...';
                    progressText.textContent = `Downloading update... ${pct}% (${downloadedMB} / ${totalMB} MB)`;
                }
                
                // Reset interval on progress
                this.pollInterval = 800;
                this.nextCheckTime = now + this.pollInterval;
            } else if (st === 'ready') {
                // Download complete
                this.stop();
                // ... handle ready state ...
            } else if (st === 'failed' || st === 'canceled') {
                this.stop();
                // ... handle failure ...
            } else {
                // Exponential backoff: 800ms → 1.2s → 1.8s → 2.7s → 4s
                this.pollInterval = Math.min(
                    this.pollInterval * 1.5,
                    this.maxInterval
                );
                this.nextCheckTime = now + this.pollInterval;
            }
        } catch (e) {
            console.error('Progress poll error:', e);
            // Exponential backoff on error
            this.pollInterval = Math.min(
                this.pollInterval * 1.5,
                this.maxInterval
            );
            this.nextCheckTime = now + this.pollInterval;
        } finally {
            this.isPolling = false;
        }
    }
    
    stop() {
        if (this.pollingTimer) {
            clearInterval(this.pollingTimer);
            this.pollingTimer = null;
        }
    }
}

// Usage in downloadAndInstallUpdate:
let updateProgressPoller = null;

async function downloadAndInstallUpdate() {
    if (!currentUpdateInfo) return;
    
    // ... setup UI ...
    
    // Start polling with exponential backoff
    updateProgressPoller = new UpdateProgressPoller();
    updateProgressPoller.start();
    
    // Kick off download
    try {
        const response = await fetch('/api/updates/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentUpdateInfo)
        });
        
        if (!response.ok && response.status !== 202) {
            throw new Error('Failed to start download');
        }
    } catch (e) {
        updateProgressPoller.stop();
        showNotification('Error starting update download: ' + e.message, 'error');
    }
}
```

**Checklist:**
- [ ] Create `UpdateProgressPoller` class
- [ ] Replace polling logic in `downloadAndInstallUpdate`
- [ ] Test download progress updates
- [ ] Verify exponential backoff (800ms → 1.2s → 1.8s → 2.7s → 4s)
- [ ] Test max wait time (10 minutes)
- [ ] Test cancellation stops polling
- [ ] Verify request count reduced from 75 to ~15 per minute

---

### Task 3.2: Add Exponential Backoff to Mobile Inbox Polling
**File:** `assets/static/js/app/mobile-inbox.js:579-584`
**Severity:** 🟡 MEDIUM
**Estimated Impact:** 60% reduction in requests (6 → 2.4 req/min)
**Time:** 15 minutes

**Current Code:**
```javascript
function startPolling() {
    if (pollingTimer) return;
    pollingTimer = window.setInterval(pollInboxOnce, 10000);  // Every 10 seconds
    pollInboxOnce();
}
```

**Fix:**
```javascript
let inboxPollingInterval = 10000;  // Start at 10 seconds
let inboxNextCheckTime = 0;
let inboxPollingTimer = null;
let inboxLastCheckTime = 0;

function startInboxPolling() {
    if (inboxPollingTimer) return;
    
    inboxPollingTimer = window.setInterval(() => {
        const now = Date.now();
        
        // Exponential backoff: 10s → 15s → 22s → 30s
        if (now >= inboxNextCheckTime) {
            pollInboxOnce();
            inboxLastCheckTime = now;
            inboxNextCheckTime = now + inboxPollingInterval;
        }
    }, 1000);  // Check every 1 second if it's time
    
    pollInboxOnce();  // Check immediately
}

async function pollInboxOnce() {
    if (pollingInFlight) return;
    if (document.hidden) return;
    
    pollingInFlight = true;
    
    try {
        const data = await fetchJson('/api/mobile/inbox/pending', { cacheTTL: 0 });
        
        if (!data || !data.success) {
            updateInboxIndicator(0);
            // Exponential backoff on error
            inboxPollingInterval = Math.min(inboxPollingInterval * 1.5, 30000);
            return;
        }
        
        const pending = data.pending;
        if (!pending || !pending.id) {
            currentPendingSubmissionId = null;
            updateInboxIndicator(0);
            // Exponential backoff when no pending
            inboxPollingInterval = Math.min(inboxPollingInterval * 1.5, 30000);
            return;
        }
        
        // Found pending submission - reset interval
        inboxPollingInterval = 10000;
        
        const payload = pending.payload || {};
        const tasks = Array.isArray(payload.tasks) ? payload.tasks : [];
        const notes = Array.isArray(payload.notes) ? payload.notes : [];
        updateInboxIndicator(tasks.length + notes.length);
        
        if (currentPendingSubmissionId === pending.id) {
            return;
        }
        
        currentPendingSubmissionId = pending.id;
        renderInboxList(pending);
        open('mobile-inbox-modal');
    } catch (e) {
        updateInboxIndicator(0);
        // Exponential backoff on error
        inboxPollingInterval = Math.min(inboxPollingInterval * 1.5, 30000);
    } finally {
        pollingInFlight = false;
    }
}

function stopInboxPolling() {
    if (inboxPollingTimer) {
        clearInterval(inboxPollingTimer);
        inboxPollingTimer = null;
    }
    inboxPollingInterval = 10000;  // Reset
}
```

**Checklist:**
- [ ] Add exponential backoff variables
- [ ] Update `startInboxPolling()` function
- [ ] Update `pollInboxOnce()` to use backoff
- [ ] Add `stopInboxPolling()` function
- [ ] Test polling starts at 10s
- [ ] Test backoff increases: 10s → 15s → 22s → 30s
- [ ] Test resets to 10s when pending found
- [ ] Verify request count reduced from 6 to ~2.4 per minute

---

### Task 3.3: Add Exponential Backoff to Companion Sync Polling
**File:** `assets/static/js/app/companion-sync.js:44-82`
**Severity:** 🟡 MEDIUM
**Estimated Impact:** 60% reduction in requests (12 → 4.8 req/90s)
**Time:** 15 minutes

**Current Code:**
```javascript
const SYNC_POLL_INTERVAL_MS = 5000;  // 5 seconds
const SYNC_POLL_MAX_TICKS = 18;      // 90 seconds max

function _startSyncRequestPoll() {
    _stopSyncRequestPoll();
    _syncRequestPollInterval = setInterval(_syncRequestPollTick, SYNC_POLL_INTERVAL_MS);
}
```

**Fix:**
```javascript
let _syncPollInterval = 5000;  // Start at 5 seconds
let _syncNextCheckTime = 0;
let _syncPollingTimer = null;
const SYNC_POLL_MAX_INTERVAL = 30000;  // Max 30 seconds
const SYNC_POLL_MAX_WAIT = 90000;  // 90 seconds total
let _syncPollStartTime = 0;

function _startSyncRequestPoll() {
    _stopSyncRequestPoll();
    _syncPollStartTime = Date.now();
    _syncPollInterval = 5000;
    _syncNextCheckTime = 0;
    
    _syncPollingTimer = setInterval(() => {
        const now = Date.now();
        
        // Give up after 90 seconds
        if (now - _syncPollStartTime > SYNC_POLL_MAX_WAIT) {
            _stopSyncRequestPoll();
            return;
        }
        
        // Check if it's time to poll
        if (now >= _syncNextCheckTime) {
            _syncRequestPollTick();
            _syncNextCheckTime = now + _syncPollInterval;
        }
    }, 500);  // Check every 500ms if it's time
}

async function _syncRequestPollTick() {
    try {
        const resp = await fetch('/api/mobile/inbox/pending', { credentials: 'include' });
        if (!resp.ok) {
            // Exponential backoff on error
            _syncPollInterval = Math.min(_syncPollInterval * 1.5, SYNC_POLL_MAX_INTERVAL);
            return;
        }
        
        const data = await resp.json();
        if (!data.success || !data.pending || !data.pending.id) {
            // Exponential backoff when no pending
            _syncPollInterval = Math.min(_syncPollInterval * 1.5, SYNC_POLL_MAX_INTERVAL);
            return;
        }
        
        const pl = data.pending.payload || {};
        const total = (Array.isArray(pl.tasks) ? pl.tasks.length : 0)
                    + (Array.isArray(pl.notes) ? pl.notes.length : 0);
        
        if (total > 0) {
            // Found pending - stop polling and show modal
            _stopSyncRequestPoll();
            showCompanionSyncModal(data.pending);
        } else {
            // No items - exponential backoff
            _syncPollInterval = Math.min(_syncPollInterval * 1.5, SYNC_POLL_MAX_INTERVAL);
        }
    } catch (e) {
        console.debug('Sync request poll error:', e);
        // Exponential backoff on error
        _syncPollInterval = Math.min(_syncPollInterval * 1.5, SYNC_POLL_MAX_INTERVAL);
    }
}

function _stopSyncRequestPoll() {
    if (_syncPollingTimer) {
        clearInterval(_syncPollingTimer);
        _syncPollingTimer = null;
    }
    _syncPollInterval = 5000;  // Reset
}
```

**Checklist:**
- [ ] Add exponential backoff variables
- [ ] Update `_startSyncRequestPoll()` function
- [ ] Update `_syncRequestPollTick()` to use backoff
- [ ] Update `_stopSyncRequestPoll()` function
- [ ] Test polling starts at 5s
- [ ] Test backoff increases: 5s → 7.5s → 11s → 16s → 30s
- [ ] Test max wait time (90 seconds)
- [ ] Verify request count reduced from 12 to ~4.8 per 90 seconds

---

## 🟢 PHASE 4: MINOR FIXES

### Task 4.1: Fix QR Code Timer Cleanup
**File:** `assets/static/js/app/mobile-inbox.js:115-178`
**Severity:** 🟡 MEDIUM
**Time:** 10 minutes

**Current Code:**
```javascript
let qrRefreshTimer = null;

async function refreshPairingCode() {
    // ... fetch code ...
    
    if (qrRefreshTimer) {
        clearTimeout(qrRefreshTimer);
        qrRefreshTimer = null;
    }
    
    const refreshDelay = Math.max((expiresIn - 30) * 1000, 30000);
    qrRefreshTimer = setTimeout(() => {
        const modal = getEl('pair-phone-modal');
        if (modal && (modal.classList.contains('active') || modal.style.display === 'flex')) {
            refreshPairingCode();  // ← Recursive
        }
    }, refreshDelay);
}
```

**Fix:**
```javascript
let qrRefreshTimer = null;

async function refreshPairingCode() {
    const statusEl = getEl('pair-phone-status');
    const codeEl = getEl('pair-phone-code');
    const urlEl = getEl('pair-phone-url');
    
    if (statusEl) statusEl.textContent = 'Loading…';
    if (codeEl) codeEl.textContent = '';
    if (urlEl) urlEl.textContent = '';
    clearQr();
    
    // Clear any existing timer
    if (qrRefreshTimer) {
        clearTimeout(qrRefreshTimer);
        qrRefreshTimer = null;
    }
    
    try {
        const data = await fetchJson('/api/mobile/pairing');
        if (!data || !data.success) {
            throw new Error((data && data.error) ? data.error : 'Failed to create pairing code');
        }
        
        const code = String(data.code || '').trim();
        const lanUrl = data.lan_url || '';
        const expiresIn = data.expires_in || 300;
        
        if (statusEl) statusEl.textContent = 'Scan this QR in your phone app or enter the code manually.';
        if (codeEl) codeEl.textContent = code;
        if (urlEl) urlEl.textContent = lanUrl;
        
        // Update web companion URL
        const webCompanionUrlEl = getEl('web-companion-url');
        if (webCompanionUrlEl && lanUrl) {
            try {
                const urlObj = new URL(lanUrl);
                const companionUrl = `${urlObj.protocol}//${urlObj.host}/companion`;
                webCompanionUrlEl.textContent = companionUrl;
                webCompanionUrlEl.dataset.url = companionUrl;
                renderWebCompanionQr(companionUrl);
            } catch (e) {
                webCompanionUrlEl.textContent = 'Could not determine URL';
                clearWebCompanionQr();
            }
        }
        
        const qrPayload = JSON.stringify({ url: lanUrl, code });
        renderQr(qrPayload);
        
        // Schedule refresh before expiry
        const refreshDelay = Math.max((expiresIn - 30) * 1000, 30000);
        qrRefreshTimer = setTimeout(() => {
            // Only refresh if modal is still open
            const modal = getEl('pair-phone-modal');
            if (modal && (modal.classList.contains('active') || modal.style.display === 'flex')) {
                refreshPairingCode();
            }
        }, refreshDelay);
        
    } catch (e) {
        if (statusEl) statusEl.textContent = e.message || 'Failed to create pairing code';
    }
}

function closePairPhoneModal() {
    close('pair-phone-modal');
    
    // Clean up timer
    if (qrRefreshTimer) {
        clearTimeout(qrRefreshTimer);
        qrRefreshTimer = null;
    }
}
```

**Checklist:**
- [ ] Add timer cleanup in `closePairPhoneModal()`
- [ ] Ensure timer is cleared on error
- [ ] Test modal close clears timer
- [ ] Test refresh still works

---

### Task 4.2: Remove Fake Progress Simulation
**File:** `assets/static/js/app/backup-update.js:204-214`
**Severity:** 🟡 MEDIUM
**Time:** 5 minutes

**Current Code:**
```javascript
let fakePct = 0;
let progressTimer = null;
if (progressDiv && progressFill && progressText) {
    progressTimer = setInterval(() => {
        if (fakePct < 95) {
            fakePct += 3;
            progressFill.style.width = Math.min(fakePct, 95) + '%';
            progressText.textContent = 'Downloading update...';
        }
    }, 500);
}
```

**Fix:**
```javascript
// Remove fake progress simulation entirely
// Real progress is handled by the UpdateProgressPoller class
// which gets actual data from /api/updates/progress
```

**Checklist:**
- [ ] Remove fake progress code
- [ ] Verify real progress from UpdateProgressPoller is used
- [ ] Test progress bar updates with real data

---

## Summary

**Total Estimated Time:** ~4-5 hours
**Expected Performance Improvement:**
- Database operations: 10-50x faster
- API polling: 60-80% fewer requests
- Update checks: Graceful shutdown, proper resource cleanup

**Priority Order:**
1. Phase 1 (Database) - Highest impact, 2-3 hours
2. Phase 2 (Threading) - Critical for stability, 1-1.5 hours
3. Phase 3 (Polling) - Network efficiency, 1 hour
4. Phase 4 (Minor) - Polish, 15 minutes

