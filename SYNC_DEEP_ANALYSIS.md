# Deep Sync Logic Analysis - Detailed Technical Review

## Executive Summary

The companion sync system has **critical race conditions**, **data consistency issues**, and **architectural flaws** that can lead to:
- Lost sync requests on app restart
- Duplicate task imports
- Orphaned submissions in database
- Race condition deadlocks
- Memory leaks

---

## 1. Data Flow Analysis

### 1.1 Complete Sync Sequence

```
TIMELINE: Desktop → Mobile → Desktop → Mobile

T0: User clicks "Sync" on desktop
    ├─ Desktop: POST /api/mobile/request-sync
    │  └─ Backend: _sync_requested[user_id] = timestamp (IN-MEMORY, NO PERSISTENCE)
    │
T1-T5: Mobile polls GET /api/mobile/sync-request every 1-5 seconds
    ├─ Mobile: GET /api/mobile/sync-request
    │  └─ Backend: Check if user_id in _sync_requested
    │     └─ If YES: Delete from dict, return sync_requested=true
    │     └─ If NO: Return sync_requested=false
    │
T6: Mobile receives sync_requested=true
    ├─ Mobile: Prepares tasks/notes
    │  └─ Mobile: POST /api/mobile/inbox with payload
    │     └─ Backend: save_mobile_inbox_submission()
    │        ├─ INSERT INTO mobile_inbox (status='pending')
    │        └─ UPDATE mobile_devices SET last_seen_at
    │
T7-T10: Desktop polls GET /api/mobile/inbox/pending every 5-30 seconds
    ├─ Desktop: GET /api/mobile/inbox/pending
    │  └─ Backend: load_next_pending_mobile_inbox()
    │     └─ SELECT * FROM mobile_inbox WHERE status='pending' LIMIT 1
    │
T11: Desktop receives pending submission
    ├─ Desktop: Shows modal with tasks/notes
    │  └─ User selects which items to import
    │
T12: User clicks "Import"
    ├─ Desktop: POST /api/mobile/inbox/{id}/approve
    │  └─ Backend: approve_inbox()
    │     ├─ FOR EACH selected task:
    │     │  └─ create_task_for_user() → INSERT INTO tasks
    │     ├─ FOR EACH selected note:
    │     │  └─ create_note_for_user() → INSERT INTO notes
    │     └─ UPDATE mobile_inbox SET status='approved'
    │
T13: Mobile polls GET /api/mobile/inbox/{id}/status
    ├─ Mobile: GET /api/mobile/inbox/{id}/status
    │  └─ Backend: get_mobile_inbox_status()
    │     └─ SELECT status FROM mobile_inbox WHERE id=?
    │
T14: Mobile receives status='approved'
    ├─ Mobile: Deletes synced tasks from phone
    │  └─ (This is mobile app logic, not shown here)
```

---

## 2. Critical Race Conditions

### 2.1 Race Condition #1: Lost Sync Request on App Restart

**Scenario:**
```
T0: Desktop: POST /request-sync
    └─ _sync_requested['user1'] = '2026-05-04T14:26:00'

T1: Mobile: GET /sync-request
    └─ Reads _sync_requested['user1'] = true
    └─ Deletes from dict: del _sync_requested['user1']
    └─ Returns sync_requested=true

T2: Mobile: Starts preparing tasks (async operation)
    └─ Takes 5 seconds...

T3: DESKTOP APP CRASHES AND RESTARTS
    └─ _sync_requested dict is cleared (in-memory only)
    └─ All pending sync requests are LOST

T7: Mobile: POST /inbox with tasks
    └─ Backend: save_mobile_inbox_submission()
    └─ Creates submission in database with status='pending'

T8: Desktop (restarted): GET /inbox/pending
    └─ Finds submission and shows modal
    └─ User imports tasks
    └─ BUT: Desktop never sent the original sync request!
```

**Impact:** 
- User presses Sync → app crashes → user manually syncs again
- Confusing UX, data loss risk

**Root Cause:**
```python
# mobile_routes.py:28
_sync_requested: Dict[str, str] = {}  # ← IN-MEMORY ONLY!
```

**Fix Required:**
```python
# Move to database with TTL
# Table: mobile_sync_requests
# Columns: user_id, requested_at, expires_at (5 min TTL)
# Add cleanup job to remove expired requests
```

---

### 2.2 Race Condition #2: Concurrent Submissions from Multiple Devices

**Scenario:**
```
Device A (Phone 1)          Device B (Phone 2)          Desktop
    │                            │                          │
    │ POST /inbox (5 tasks)      │                          │
    ├──────────────────────────────────────────────────────>│
    │                            │ POST /inbox (3 tasks)    │
    │                            ├──────────────────────────>│
    │                            │                          │
    │                            │                    GET /inbox/pending
    │                            │                    ├─────────────────>
    │                            │                    │ Returns Device A
    │                            │                    │ (oldest by created_at)
    │                            │                    │
    │                            │                    User imports Device A
    │                            │                    POST /approve (Device A)
    │                            │                    │
    │                            │                    GET /inbox/pending
    │                            │                    ├─────────────────>
    │                            │                    │ Returns Device B
    │                            │                    │
    │                            │                    User imports Device B
```

**Issue:** Works correctly IF processed sequentially. But what if:

```
Device A: POST /inbox (5 tasks)  ─────┐
Device B: POST /inbox (3 tasks)  ─────┤
                                       ├─> Both INSERT simultaneously
                                       │
Desktop: GET /inbox/pending  ─────────┘
         └─ Which one is returned?
            └─ Depends on SQLite lock contention
               └─ Could be either A or B (non-deterministic)
```

**Root Cause:**
- No submission queue ordering guarantee
- SQLite's FIFO lock behavior is not guaranteed across concurrent writes
- `created_at` is set by mobile, not server (clock skew possible)

**Evidence:**
```python
# sqlite_data_manager.py:3450-3454
cur = conn.execute(
    '''
    SELECT id, device_id, device_name, payload_json, created_at
    FROM mobile_inbox
    WHERE user_id = ? AND status = 'pending'
    ORDER BY created_at ASC
    LIMIT 1
    ''',
    (user_id,),
)
```

**Fix Required:**
```python
# Use server-side timestamp instead of mobile timestamp
# Add sequence number for ordering
# Table: mobile_inbox
# Columns: id, user_id, ..., server_created_at, sequence_num
# ORDER BY sequence_num ASC (auto-increment)
```

---

### 2.3 Race Condition #3: Concurrent Approve/Reject

**Scenario:**
```
Desktop 1: POST /approve (Device A)
Desktop 2: POST /reject (Device A)
           (Same submission_id, same user)
           
Both execute simultaneously:
├─ Desktop 1: UPDATE mobile_inbox SET status='approved' WHERE id=?
├─ Desktop 2: UPDATE mobile_inbox SET status='rejected' WHERE id=?
│
Result: Whichever UPDATE executes last wins
        (Non-deterministic state)
```

**Root Cause:**
```python
# mobile_routes.py:405-519 (approve_inbox)
# mobile_routes.py:551-573 (reject_inbox)
# No mutual exclusion between approve and reject
```

**Current Code:**
```python
@mobile_bp.route("/inbox/<submission_id>/approve", methods=["POST"])
def approve_inbox(submission_id: str):
    # ... no lock ...
    dm.mark_mobile_inbox_approved(user_id, submission_id, result, now)

@mobile_bp.route("/inbox/<submission_id>/reject", methods=["POST"])
def reject_inbox(submission_id: str):
    # ... no lock ...
    dm.mark_mobile_inbox_rejected(user_id, submission_id, now)
```

**Fix Required:**
```python
# Add submission-level lock
_submission_locks: Dict[str, threading.Lock] = {}

def _get_submission_lock(submission_id: str) -> threading.Lock:
    if submission_id not in _submission_locks:
        _submission_locks[submission_id] = threading.Lock()
    return _submission_locks[submission_id]

@mobile_bp.route("/inbox/<submission_id>/approve", methods=["POST"])
def approve_inbox(submission_id: str):
    with _get_submission_lock(submission_id):
        # ... approve logic ...
```

---

### 2.4 Race Condition #4: Sync Request Consumed Twice

**Scenario:**
```
Mobile 1: GET /sync-request
          ├─ Reads _sync_requested['user1'] = true
          └─ Starts to delete...

Mobile 2: GET /sync-request (concurrent)
          ├─ Reads _sync_requested['user1'] = true
          └─ Also tries to delete...

Result: Both mobiles think they received sync request
        Both upload tasks
        Both get imported (duplicates!)
```

**Root Cause:**
```python
# mobile_routes.py:588-602
@mobile_bp.route("/sync-request", methods=["GET"])
def check_sync_request():
    user_id = device.get("user_id")
    requested = user_id in _sync_requested  # ← Read
    if requested:
        del _sync_requested[user_id]        # ← Delete (not atomic!)
    return jsonify({"success": True, "sync_requested": requested})
```

**Issue:** Read-then-delete is not atomic. Between read and delete, another request could read the same value.

**Fix Required:**
```python
# Use atomic operation
_sync_requested_lock = threading.Lock()

@mobile_bp.route("/sync-request", methods=["GET"])
def check_sync_request():
    with _sync_requested_lock:
        user_id = device.get("user_id")
        requested = user_id in _sync_requested
        if requested:
            del _sync_requested[user_id]
    return jsonify({"success": True, "sync_requested": requested})
```

---

## 3. Data Consistency Issues

### 3.1 Orphaned Submissions

**Scenario:**
```
T0: Mobile: POST /inbox (5 tasks)
    └─ Backend: INSERT INTO mobile_inbox (status='pending')

T1: Desktop: GET /inbox/pending
    └─ Returns submission

T2: User closes desktop app WITHOUT approving/rejecting

T3: Submission stays in database forever
    └─ Status='pending'
    └─ Blocks other submissions from being processed
    └─ No cleanup mechanism
```

**Evidence:**
```python
# sqlite_data_manager.py:3443-3476
def load_next_pending_mobile_inbox(self, user_id: str):
    """Return the OLDEST pending inbox submission"""
    cur = conn.execute(
        '''
        SELECT ... FROM mobile_inbox
        WHERE user_id = ? AND status = 'pending'
        ORDER BY created_at ASC
        LIMIT 1
        ''',
    )
```

**Impact:**
- If first submission is orphaned, all subsequent submissions are blocked
- No way to recover without manual database intervention

**Fix Required:**
```python
# Add timeout-based cleanup
# If submission is pending for > 24 hours, auto-reject
# Add cleanup job that runs every hour

def cleanup_stale_submissions():
    cutoff = datetime.now() - timedelta(hours=24)
    dm.mark_submissions_older_than_rejected(cutoff)
```

---

### 3.2 Partial Import Failures

**Scenario:**
```
Mobile sends: [Task1, Task2, Task3, Task4, Task5]

Desktop: POST /approve with selected_task_ids=[1,2,3,4,5]

Backend processes:
├─ Task1: ✓ Created
├─ Task2: ✓ Created
├─ Task3: ✗ FAILS (validation error)
├─ Task4: ✓ Created
├─ Task5: ✓ Created

Result: 4 tasks imported, 1 failed
        Submission marked as 'approved'
        No way to retry Task3
```

**Current Code:**
```python
# mobile_routes.py:452-493
for t in tasks:
    ok_map, task_payload, msg = _map_mobile_task_to_task_payload(t)
    if not ok_map:
        skipped.append({"client_task_id": client_task_id, "error": msg})
        continue  # ← Skip and continue, no rollback
    
    created = dm.create_task_for_user(user_id, task_payload)
    if created:
        created_tasks.append(created)
    else:
        skipped.append({"client_task_id": client_task_id, "error": "Create failed"})
```

**Issue:**
- No rollback on partial failure
- Skipped tasks are not retryable
- User doesn't know which tasks failed

**Fix Required:**
```python
# Option 1: Atomic all-or-nothing
# If any task fails, rollback all and return error

# Option 2: Partial with retry queue
# Store failed tasks in retry_queue table
# Allow user to retry failed tasks later
```

---

### 3.3 Duplicate Task Detection Missing

**Scenario:**
```
Desktop: Has "Buy groceries" (due: 2026-05-05)

Mobile: Creates "Buy groceries" (due: 2026-05-05)
        Syncs to desktop

Result: Two identical tasks in desktop
        User confused, has to manually delete one
```

**Current Code:**
```python
# mobile_routes.py:363-402
def _map_mobile_task_to_task_payload(mobile_task):
    title = mobile_task.get("title")
    due_date = mobile_task.get("due_date")
    # ... creates task payload ...
    # NO DUPLICATE CHECK!
```

**Fix Required:**
```python
def _find_duplicate_task(user_id, title, due_date):
    """Check if task with same title and due_date exists"""
    tasks = dm.load_tasks_for_user(user_id)
    for t in tasks:
        if (t.get('title') == title and 
            t.get('due_date') == due_date and
            not t.get('completed')):
            return t
    return None

# In approve_inbox:
for t in tasks:
    if _find_duplicate_task(user_id, t['title'], t['due_date']):
        skipped.append({"client_task_id": id, "error": "Duplicate task exists"})
        continue
```

---

## 4. Polling Architecture Issues

### 4.1 Polling Latency Analysis

**Current Implementation:**
```javascript
// companion-sync.js:43-47
let _syncPollInterval = 5000;  // Start at 5 seconds
const SYNC_POLL_MAX_INTERVAL = 30000;  // Max 30 seconds
const SYNC_POLL_MAX_WAIT = 90000;  // 90 seconds total

// companion-sync.js:95-109
_syncPollingTimer = setInterval(() => {
    const now = Date.now();
    if (now - _syncPollStartTime > SYNC_POLL_MAX_WAIT) {
        _stopSyncRequestPoll();
        return;
    }
    if (now >= _syncNextCheckTime) {
        _syncRequestPollTick();
        _syncNextCheckTime = now + _syncPollInterval;
    }
}, 500);  // Check every 500ms if it's time
```

**Latency Breakdown:**
```
Best case (immediate):
├─ T0: User clicks Sync
├─ T0.5: Desktop sends request
├─ T1: Mobile polls (within 1 second)
└─ Total: ~1 second

Worst case (unlucky timing):
├─ T0: User clicks Sync
├─ T0.5: Desktop sends request
├─ T0.6: Mobile just finished polling (bad timing)
├─ T5.6: Mobile polls again (5 second interval)
├─ T5.6: Mobile sees request
├─ T5.7: Mobile starts preparing tasks (5 seconds)
├─ T10.7: Mobile sends tasks
├─ T10.8: Desktop polls (bad timing again)
├─ T15.8: Desktop polls again (5 second interval)
├─ T15.8: Desktop sees submission
├─ T15.9: Desktop shows modal
└─ Total: ~15 seconds (worst case up to 90 seconds)
```

**Issues:**
1. **Exponential backoff resets on every error** - If network is flaky, backoff never reaches max
2. **No jitter** - If 100 users sync at same time, all poll at same moment (thundering herd)
3. **500ms timer tick is wasteful** - Could use `setTimeout` instead of `setInterval`
4. **Polling continues after modal shown** - Unnecessary network requests

**Fix Required:**
```javascript
// Implement WebSocket or Server-Sent Events
// Or add jitter to polling:
const jitter = Math.random() * 1000; // 0-1 second random
_syncNextCheckTime = now + _syncPollInterval + jitter;
```

---

### 4.2 Mobile Polling Overhead

**Current Flow:**
```
Mobile: Every 2 hours, calls checkCompanionTasksSync()
        ├─ GET /api/mobile/inbox/pending
        ├─ If empty, calls POST /api/mobile/request-sync
        ├─ Then starts polling every 5-30 seconds
        │  └─ For up to 90 seconds
        │  └─ Even if no tasks available
        │
        └─ Wakes up phone, uses battery, uses data
```

**Battery Impact:**
```
Scenario: 2-hour auto-sync interval
├─ Every 2 hours: 1 request to check inbox
├─ If empty: Starts 90-second polling window
│  └─ 5s → 7.5s → 11.25s → 16.87s → 25.3s → 30s (max)
│  └─ ~6-7 requests per sync attempt
│
├─ Per day: 12 sync checks × 7 requests = 84 requests
├─ Plus: Exponential backoff means requests cluster
│  └─ Wakes phone up multiple times
│  └─ Prevents deep sleep
│
└─ Battery drain: Significant over time
```

**Fix Required:**
- Implement push notifications instead of polling
- Or use WebSocket with keep-alive
- Or increase polling interval to 30s from start

---

## 5. Memory Leak Analysis

### 5.1 _sync_requested Dictionary

**Scenario:**
```
Day 1: 10 users sync
       _sync_requested = {user1, user2, ..., user10}

Day 2: 10 more users sync
       _sync_requested = {user1, user2, ..., user20}

Day 30: 300 users have synced
        _sync_requested = {user1, user2, ..., user300}
        
But: Some requests are never consumed!
     └─ If mobile never polls, request stays forever
     └─ If mobile crashes before consuming, request stays forever
     └─ If network fails, request stays forever
```

**Impact:**
```
Memory usage:
├─ Per entry: ~100 bytes (user_id + timestamp)
├─ 300 users × 100 bytes = 30 KB
├─ 1000 users × 100 bytes = 100 KB
├─ 10000 users × 100 bytes = 1 MB

Not huge, but:
├─ Grows indefinitely
├─ App restarts lose all data anyway
├─ Better to use database with TTL
```

**Fix Required:**
```python
# Add cleanup job
def cleanup_expired_sync_requests():
    now = datetime.now()
    expired = [
        uid for uid, ts in _sync_requested.items()
        if (now - datetime.fromisoformat(ts)).total_seconds() > 300  # 5 min TTL
    ]
    for uid in expired:
        del _sync_requested[uid]
    
# Run every 5 minutes
scheduler.schedule_job('cleanup_sync_requests', cleanup_expired_sync_requests, trigger='interval', minutes=5)
```

---

### 5.2 _submission_locks Dictionary

**Potential Issue:**
```python
# If we add submission-level locks (recommended fix):
_submission_locks: Dict[str, threading.Lock] = {}

def _get_submission_lock(submission_id: str):
    if submission_id not in _submission_locks:
        _submission_locks[submission_id] = threading.Lock()
    return _submission_locks[submission_id]
```

**Problem:**
- Locks are never removed
- After submission is approved/rejected, lock stays in memory
- Over time, accumulates locks for all submissions ever created

**Fix Required:**
```python
def _get_submission_lock(submission_id: str):
    if submission_id not in _submission_locks:
        _submission_locks[submission_id] = threading.Lock()
    return _submission_locks[submission_id]

# After submission is processed:
def cleanup_submission_lock(submission_id: str):
    if submission_id in _submission_locks:
        del _submission_locks[submission_id]

# Call after approve/reject:
cleanup_submission_lock(submission_id)
```

---

## 6. State Machine Issues

### 6.1 Submission State Transitions

**Current States:**
```
pending → approved
pending → rejected
```

**Issues:**
1. **No "processing" state** - Can't distinguish between "waiting to be processed" and "being processed"
2. **No "expired" state** - Orphaned submissions stay pending forever
3. **No "failed" state** - Can't mark partial failures
4. **No "retry" state** - Can't retry failed imports

**Recommended State Machine:**
```
pending
  ├─ → processing (when desktop starts importing)
  │   ├─ → approved (all tasks imported successfully)
  │   ├─ → partial (some tasks imported, some failed)
  │   └─ → failed (all tasks failed)
  │
  ├─ → rejected (user skipped)
  │
  └─ → expired (> 24 hours old, auto-rejected)

partial → retry (user retries failed tasks)
failed → retry (user retries)
```

---

## 7. Security Issues

### 7.1 No Rate Limiting

**Current Code:**
```python
@mobile_bp.route("/inbox", methods=["POST"])
def submit_inbox():
    # NO RATE LIMITING!
    # Mobile can spam this endpoint
```

**Attack Scenario:**
```
Attacker with valid token:
├─ POST /inbox 1000 times per second
├─ Database fills up with submissions
├─ Desktop app becomes slow (querying 1000 pending submissions)
├─ Legitimate users can't sync
```

**Fix Required:**
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

@mobile_bp.route("/inbox", methods=["POST"])
@limiter.limit("10 per minute")  # Per device
def submit_inbox():
    # ...
```

---

### 7.2 Timestamp Validation Missing

**Current Code:**
```python
# mobile_routes.py:303
submission_id = str(data.get("submission_id") or "").strip() or str(uuid.uuid4())

# sqlite_data_manager.py:3430
payload_json, created_at_iso
```

**Issue:**
- Mobile provides `created_at` timestamp
- No validation that timestamp is reasonable
- Mobile could provide future timestamp or very old timestamp
- Affects ordering of submissions

**Fix Required:**
```python
def validate_timestamp(timestamp_iso: str) -> bool:
    try:
        ts = datetime.fromisoformat(timestamp_iso)
        now = datetime.now()
        # Timestamp must be within 1 hour of now
        if abs((now - ts).total_seconds()) > 3600:
            return False
        return True
    except:
        return False

# In submit_inbox:
created_at = data.get("created_at") or datetime.now().isoformat()
if not validate_timestamp(created_at):
    created_at = datetime.now().isoformat()
```

---

## 8. Summary Table: All Issues

| # | Issue | Severity | Category | Impact | Effort |
|---|-------|----------|----------|--------|--------|
| 1 | Lost sync request on restart | 🔴 Critical | Reliability | Data loss | Medium |
| 2 | Concurrent submissions race | 🔴 Critical | Data | Non-deterministic order | Medium |
| 3 | Concurrent approve/reject | 🔴 Critical | Data | Inconsistent state | Low |
| 4 | Sync request consumed twice | 🔴 Critical | Reliability | Duplicate imports | Low |
| 5 | Orphaned submissions | 🟡 Major | Stability | Blocks sync | Low |
| 6 | Partial import failures | 🟡 Major | UX | Data loss | Medium |
| 7 | No duplicate detection | 🟡 Major | Data | Duplicate tasks | Medium |
| 8 | Polling latency (up to 90s) | 🟡 Major | Performance | Poor UX | High |
| 9 | Mobile polling overhead | 🟡 Major | Performance | Battery drain | High |
| 10 | Memory leak (sync requests) | 🟠 Minor | Stability | Grows over time | Low |
| 11 | Memory leak (submission locks) | 🟠 Minor | Stability | Grows over time | Low |
| 12 | No state machine | 🟠 Minor | Architecture | Poor tracking | Medium |
| 13 | No rate limiting | 🟠 Minor | Security | DoS risk | Low |
| 14 | No timestamp validation | 🟠 Minor | Security | Ordering issues | Low |

---

## 9. Recommended Fix Priority

### Phase 1: Critical Fixes (2 days)
1. Add threading lock to sync request read-delete
2. Add submission-level locks for approve/reject
3. Add orphaned submission cleanup job
4. Move sync state to database with TTL

### Phase 2: Major Fixes (1 week)
5. Implement submission queue with sequence numbers
6. Add duplicate task detection
7. Add partial failure handling with retry queue
8. Improve error messages

### Phase 3: Architecture Improvements (2 weeks)
9. Replace polling with WebSocket/SSE
10. Implement proper state machine
11. Add rate limiting
12. Add timestamp validation

### Phase 4: Polish (1 week)
13. Add jitter to polling
14. Add cleanup for submission locks
15. Add comprehensive logging
16. Add monitoring/alerts

---

## 10. Testing Strategy

### Unit Tests
```python
def test_sync_request_atomic_read_delete():
    # Verify read-delete is atomic
    
def test_concurrent_approve_reject():
    # Verify only one succeeds
    
def test_orphaned_submission_cleanup():
    # Verify old submissions are cleaned up
    
def test_duplicate_detection():
    # Verify duplicates are detected
```

### Integration Tests
```python
def test_full_sync_flow():
    # Desktop → Mobile → Desktop
    
def test_concurrent_syncs():
    # Multiple devices syncing simultaneously
    
def test_partial_failure_recovery():
    # Some tasks fail, user retries
    
def test_sync_request_persistence():
    # Sync request survives app restart
```

### Load Tests
```python
def test_1000_concurrent_submissions():
    # Verify ordering is correct
    
def test_memory_leak_over_time():
    # Verify no memory growth
```

---

## Conclusion

The sync system has **14 identified issues**, with **4 critical race conditions** that can cause data loss or inconsistency. The most urgent fixes are:

1. **Add atomic operations** for sync request handling
2. **Move sync state to database** for persistence
3. **Add submission-level locks** for mutual exclusion
4. **Implement cleanup jobs** for orphaned data

Estimated effort: **3-4 weeks** for full fix
Estimated effort: **3-4 days** for critical fixes only

The architecture would benefit from a complete redesign using WebSocket/SSE instead of polling, but the critical race conditions should be fixed immediately.
