# Sync Code Flow - Detailed Walkthrough

## User Clicks "Sync" Button on Desktop

### Step 1: Frontend Initiates Sync Check
**File:** `assets/static/js/app/companion-sync.js:84-157`

```javascript
async function checkCompanionTasksSync(isManual = false) {
    if (_syncCheckInProgress) return;  // Guard: prevent concurrent checks
    _syncCheckInProgress = true;
    
    // Set 30-second timeout guard
    _syncCheckTimeout = setTimeout(() => {
        _syncCheckInProgress = false;
    }, 30000);
    
    try {
        // Show user feedback
        window.showNotification('Checking for tasks from phone...', 'info');
        
        // FIRST: Check if phone already uploaded tasks
        const response = await fetch('/api/mobile/inbox/pending', { 
            credentials: 'include' 
        });
        
        if (response.ok) {
            const data = await response.json();
            
            // If tasks found: Show modal immediately!
            if (data.success && data.pending && data.pending.id) {
                const pending = data.pending;
                const payload = pending.payload || {};
                const tasks = Array.isArray(payload.tasks) ? payload.tasks : [];
                const notes = Array.isArray(payload.notes) ? payload.notes : [];
                
                if (tasks.length + notes.length > 0) {
                    window.showNotification(`Found ${tasks.length} tasks`, 'success');
                    showCompanionSyncModal(pending);  // ← Show modal immediately
                    return;
                }
            }
        }
        
        // SECOND: No tasks found, signal phone to upload
        if (isManual) {
            const syncResp = await fetch('/api/mobile/request-sync', {
                method: 'POST',
                credentials: 'include',
            });
            
            if (syncResp.ok) {
                window.showNotification('Sync request sent to phone...', 'info');
            }
        }
    } finally {
        clearTimeout(_syncCheckTimeout);
        _syncCheckInProgress = false;
    }
}
```

---

## Backend Receives Sync Request

### Step 2: Desktop Sends Sync Request
**File:** `src/routes/mobile_routes.py:602-627`

```python
@mobile_bp.route("/request-sync", methods=["POST"])
def request_sync():
    """Desktop signals that it wants the phone to upload tasks"""
    if not _is_local_request():
        return jsonify({"success": False, "error": "Forbidden"}), 403
    
    dm = _get_data_manager()
    user_id = _get_user_id()
    request_id = str(uuid.uuid4())
    
    # Sync request expires in 5 minutes
    expires_at = (datetime.now() + timedelta(minutes=5)).isoformat()
    
    try:
        # SAVE TO DATABASE (not in-memory dict!)
        dm.save_mobile_sync_request(user_id, request_id, expires_at)
        logger.debug("Sync requested for user %s (request_id=%s)", user_id, request_id)
        return jsonify({"success": True, "request_id": request_id})
    except Exception:
        logger.exception("Failed to save sync request")
        return jsonify({"success": False, "error": "Failed"}), 500
```

**Database Operation:**
```python
# src/sqlite_data_manager.py:3615-3633
def save_mobile_sync_request(self, user_id: str, request_id: str, expires_at_iso: str):
    """Save sync request to database with TTL"""
    self._ensure_user_exists(user_id)
    requested_at = datetime.now().isoformat()
    
    with self._get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE TRANSACTION')  # ← Atomic!
        conn.execute(
            '''
            INSERT OR REPLACE INTO mobile_sync_requests (
                id, user_id, requested_at, expires_at, consumed_at
            ) VALUES (?, ?, ?, ?, NULL)
            ''',
            (request_id, user_id, requested_at, expires_at_iso),
        )
        conn.commit()
```

---

## Phone Polls for Sync Request

### Step 3: Phone Checks for Sync Request
**File:** `src/routes/mobile_routes.py:630-654`

```python
@mobile_bp.route("/sync-request", methods=["GET"])
def check_sync_request():
    """Mobile app polls this to know if desktop requested sync"""
    ok, device, err = _require_mobile_token()
    if not ok or not device:
        return jsonify({"success": False, "error": err}), 401
    
    dm = _get_data_manager()
    user_id = device.get("user_id")
    
    try:
        # ATOMICALLY check and consume sync request
        requested = dm.get_and_consume_mobile_sync_request(user_id)
        return jsonify({"success": True, "sync_requested": requested})
    except Exception:
        logger.exception("Failed to check sync request")
        return jsonify({"success": False, "error": "Failed"}), 500
```

**Atomic Database Operation:**
```python
# src/sqlite_data_manager.py:3635-3670
def get_and_consume_mobile_sync_request(self, user_id: str) -> bool:
    """Atomically check and consume sync request"""
    with self._get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE TRANSACTION')  # ← Atomic!
        
        # Check if request exists and not yet consumed
        cur = conn.execute(
            '''
            SELECT id FROM mobile_sync_requests
            WHERE user_id = ? AND consumed_at IS NULL AND expires_at > ?
            LIMIT 1
            ''',
            (user_id, datetime.now().isoformat()),
        )
        row = cur.fetchone()
        
        if not row:
            conn.commit()
            return False
        
        # Mark as consumed (atomic with read)
        request_id = row['id']
        conn.execute(
            '''
            UPDATE mobile_sync_requests
            SET consumed_at = ?
            WHERE id = ?
            ''',
            (datetime.now().isoformat(), request_id),
        )
        conn.commit()
        return True
```

**Key Point:** The read and delete are in the same transaction, so no two mobiles can consume the same request!

---

## Phone Uploads Tasks

### Step 4: Phone Submits Tasks
**File:** `src/routes/mobile_routes.py:279-330`

```python
@mobile_bp.route("/inbox", methods=["POST"])
def submit_inbox():
    """Mobile app submits tasks/notes for import"""
    ok, device, err = _require_mobile_token()
    if not ok or not device:
        return jsonify({"success": False, "error": err}), 401
    
    data = request.json
    user_id = device.get("user_id")
    submission_id = str(uuid.uuid4())
    
    # Save submission to database
    dm.save_mobile_inbox_submission(
        user_id,
        device.get("device_id"),
        device.get("device_name"),
        submission_id,
        data,
        datetime.now().isoformat()
    )
    
    return jsonify({
        "success": True,
        "submission_id": submission_id
    })
```

---

## Desktop Fetches Tasks

### Step 5: Desktop Checks for Submitted Tasks
**File:** `src/routes/mobile_routes.py:351-372`

```python
@mobile_bp.route("/inbox/pending", methods=["GET"])
def get_pending_inbox():
    """Get oldest pending submission for user"""
    if not _is_local_request():
        return jsonify({"success": False, "error": "Forbidden"}), 403
    
    dm = _get_data_manager()
    user_id = _get_user_id()
    
    try:
        # Get oldest pending submission
        pending = dm.load_next_pending_mobile_inbox(user_id)
        
        if not pending:
            return jsonify({"success": True, "pending": None})
        
        return jsonify({
            "success": True,
            "pending": {
                "id": pending['id'],
                "device_id": pending['device_id'],
                "device_name": pending['device_name'],
                "payload": pending['payload'],
                "created_at": pending['created_at'],
            }
        })
    except Exception:
        logger.exception("Error loading pending inbox")
        return jsonify({"success": False, "error": "Error"}), 500
```

---

## User Approves Import

### Step 6: User Clicks "Import" in Modal
**File:** `src/routes/mobile_routes.py:441-545`

```python
@mobile_bp.route("/inbox/<submission_id>/approve", methods=["POST"])
def approve_inbox(submission_id: str):
    """User approves importing tasks from phone"""
    if not _is_local_request():
        return jsonify({"success": False, "error": "Forbidden"}), 403
    
    user_id = _get_user_id()
    
    # ACQUIRE SUBMISSION-LEVEL LOCK
    submission_lock = _get_submission_lock(submission_id)
    with submission_lock:  # ← Only one approve/reject can happen at a time!
        try:
            # Get submission payload
            payload = dm.get_pending_mobile_inbox_payload(user_id, submission_id)
            if payload is None:
                return jsonify({"success": False, "error": "Not found"}), 404
            
            tasks = payload.get("tasks", [])
            notes = payload.get("notes", [])
            
            # Import each task
            created_tasks = []
            for t in tasks:
                created = dm.create_task_for_user(user_id, task_payload)
                if created:
                    created_tasks.append(created)
            
            # Import each note
            created_notes = []
            for n in notes:
                created_note = dm.create_note_for_user(user_id, note_data)
                if created_note:
                    created_notes.append(created_note)
            
            # Mark submission as approved
            result = {
                "created_tasks": len(created_tasks),
                "created_notes": len(created_notes),
            }
            dm.mark_mobile_inbox_approved(user_id, submission_id, result, now)
            
            # Clean up lock
            _cleanup_submission_lock(submission_id)
            
            return jsonify({
                "success": True,
                "created_tasks": len(created_tasks),
                "created_notes": len(created_notes),
            })
        
        except Exception:
            logger.exception("Failed to approve")
            _cleanup_submission_lock(submission_id)
            return jsonify({"success": False, "error": "Failed"}), 500
```

---

## Automatic Cleanup

### Step 7: Scheduler Runs Cleanup Jobs
**File:** `src/services/scheduler.py:912-974`

```python
def _cleanup_mobile_sync_requests_job() -> None:
    """Clean up expired sync requests (runs every hour)"""
    try:
        data_manager = _get_data_manager()
        count = data_manager.cleanup_expired_sync_requests()
        if count > 0:
            logger.info(f"Cleaned up {count} expired sync requests")
    except Exception:
        logger.exception("Error cleaning up sync requests")

def _cleanup_stale_submissions_job() -> None:
    """Auto-reject old submissions (runs every 6 hours)"""
    try:
        data_manager = _get_data_manager()
        count = data_manager.cleanup_stale_submissions(hours_old=24)
        if count > 0:
            logger.info(f"Auto-rejected {count} stale submissions")
    except Exception:
        logger.exception("Error cleaning up submissions")
```

**Database Operations:**
```python
# src/sqlite_data_manager.py:3672-3714

def cleanup_expired_sync_requests(self) -> int:
    """Delete sync requests older than expiry time"""
    with self._get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE TRANSACTION')
        cur = conn.execute(
            '''
            DELETE FROM mobile_sync_requests
            WHERE expires_at < ?
            ''',
            (datetime.now().isoformat(),),
        )
        count = cur.rowcount
        conn.commit()
        return count

def cleanup_stale_submissions(self, hours_old: int = 24) -> int:
    """Auto-reject submissions older than specified hours"""
    cutoff = (datetime.now() - timedelta(hours=hours_old)).isoformat()
    with self._get_connection() as conn:
        conn.execute('BEGIN IMMEDIATE TRANSACTION')
        cur = conn.execute(
            '''
            UPDATE mobile_inbox
            SET status = 'expired', processed_at = ?
            WHERE status = 'pending' AND created_at < ?
            ''',
            (datetime.now().isoformat(), cutoff),
        )
        count = cur.rowcount
        conn.commit()
        return count
```

---

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ USER CLICKS "SYNC" ON DESKTOP                                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ DESKTOP: checkCompanionTasksSync()                              │
│ - Check /api/mobile/inbox/pending                               │
│ - If tasks exist: Show modal immediately ✅                      │
│ - If no tasks: Send /api/mobile/request-sync                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ BACKEND: POST /api/mobile/request-sync                          │
│ - Save to mobile_sync_requests table                            │
│ - Set 5-minute expiry                                           │
│ - Return request_id                                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHONE: GET /api/mobile/sync-request (polls)                     │
│ - Atomically check and consume request                          │
│ - If found: Return sync_requested=true                          │
│ - Prepare tasks/notes for upload                                │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ PHONE: POST /api/mobile/inbox                                   │
│ - Upload tasks/notes payload                                    │
│ - Backend saves to mobile_inbox table                           │
│ - Return submission_id                                          │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ DESKTOP: GET /api/mobile/inbox/pending (auto-checks)            │
│ - Fetch pending submission                                      │
│ - Show import modal                                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ USER: Selects tasks and clicks "Import"                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ DESKTOP: POST /api/mobile/inbox/{id}/approve                    │
│ - Acquire submission-level lock                                 │
│ - Create tasks/notes in database                                │
│ - Mark submission as 'approved'                                 │
│ - Release lock                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ SCHEDULER: Cleanup jobs (hourly & every 6 hours)                │
│ - Delete expired sync requests                                  │
│ - Auto-reject stale submissions                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Key Improvements

1. **No Polling** - Desktop fetches only when user clicks Sync
2. **Atomic Operations** - All database operations use `BEGIN IMMEDIATE TRANSACTION`
3. **Locks** - Submission-level locks prevent concurrent approve/reject
4. **Persistence** - Sync requests stored in database, survive app restart
5. **Cleanup** - Automatic jobs clean up expired data
6. **Timeout Guards** - 30-second timeout prevents hanging

---

## Testing the Flow

### Test 1: Normal Sync
1. Pair phone
2. Add tasks on phone
3. Click "Sync" on desktop
4. Modal appears within 1 second ✅
5. Select and import

### Test 2: App Restart
1. Click "Sync" on desktop (sync request saved)
2. Desktop app crashes and restarts
3. Sync request still in database ✅
4. Phone can still consume it

### Test 3: Concurrent Approve/Reject
1. Two desktops try to approve/reject same submission
2. Only one succeeds (lock prevents both) ✅
3. Other gets error

### Test 4: Orphaned Submission
1. Submission stays pending for 24+ hours
2. Cleanup job auto-rejects it ✅
3. New submissions can be processed
