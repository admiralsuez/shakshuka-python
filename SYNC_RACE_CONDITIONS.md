# Sync Race Conditions - Visual Diagrams

## Race Condition #1: Lost Sync Request on App Restart

```
TIMELINE: Desktop → Mobile → Desktop Crash → Desktop Restart

Desktop                          Backend                    Mobile
  │                                │                          │
  │ Click "Sync"                   │                          │
  ├──────────────────────────────>│                          │
  │ POST /request-sync             │                          │
  │                                │ _sync_requested['u1']    │
  │                                │ = '2026-05-04T14:26:00'  │
  │                                │                          │
  │                                │<─────────────────────────┤
  │                                │ GET /sync-request        │
  │                                │ (polls every 5 seconds)  │
  │                                │                          │
  │                                │ Returns: sync_requested  │
  │                                │ = true                   │
  │                                │                          │
  │                                │ del _sync_requested['u1']│
  │                                │                          │
  │                                │ Mobile starts preparing  │
  │                                │ tasks (5 seconds)        │
  │                                │                          │
  │ ❌ CRASH!                      │                          │
  │ (App restarts)                 │                          │
  │                                │ _sync_requested = {}     │
  │                                │ (IN-MEMORY CLEARED!)     │
  │                                │                          │
  │                                │                          │ POST /inbox
  │                                │                          │ (5 tasks)
  │                                │<─────────────────────────┤
  │                                │                          │
  │                                │ INSERT INTO mobile_inbox │
  │                                │ (status='pending')       │
  │                                │                          │
  │ Restart complete               │                          │
  │                                │                          │
  │ GET /inbox/pending             │                          │
  ├──────────────────────────────>│                          │
  │                                │                          │
  │ Returns submission             │                          │
  │ (but desktop never sent        │                          │
  │  the original request!)        │                          │
  │                                │                          │

PROBLEM:
- Sync request is lost when app restarts
- Submission is orphaned in database
- User confused about what happened
- No way to recover without manual intervention

SOLUTION:
- Store sync requests in database with TTL
- Add cleanup job to remove expired requests
```

---

## Race Condition #2: Concurrent Submissions from Multiple Devices

```
TIMELINE: Two phones sync simultaneously

Phone A                          Backend                    Phone B
  │                                │                          │
  │ POST /inbox (5 tasks)          │                          │
  ├──────────────────────────────>│                          │
  │                                │ INSERT INTO mobile_inbox │
  │                                │ (id='sub_A', created_at) │
  │                                │                          │
  │                                │<─────────────────────────┤
  │                                │ POST /inbox (3 tasks)    │
  │                                │                          │
  │                                │ INSERT INTO mobile_inbox │
  │                                │ (id='sub_B', created_at) │
  │                                │                          │
  │                                │ Both inserts complete    │
  │                                │                          │
  │                                │ SELECT ... FROM mobile_inbox
  │                                │ WHERE status='pending'
  │                                │ ORDER BY created_at ASC
  │                                │ LIMIT 1
  │                                │                          │
  │                                │ Which one is returned?   │
  │                                │ ├─ Depends on SQLite     │
  │                                │ │  lock contention       │
  │                                │ ├─ Depends on clock skew │
  │                                │ │  (mobile timestamps)    │
  │                                │ └─ Non-deterministic!    │
  │                                │                          │

PROBLEM:
- No guaranteed ordering of submissions
- created_at is set by mobile (clock skew possible)
- SQLite lock behavior is not deterministic
- Could process Phone B before Phone A

SOLUTION:
- Use server-side timestamp (server_created_at)
- Add auto-increment sequence number
- ORDER BY sequence_num ASC (guaranteed order)
```

---

## Race Condition #3: Concurrent Approve/Reject

```
TIMELINE: User approves on Desktop 1, rejects on Desktop 2 simultaneously

Desktop 1                        Backend                    Desktop 2
  │                                │                          │
  │ POST /approve (sub_A)          │                          │
  ├──────────────────────────────>│                          │
  │                                │ UPDATE mobile_inbox      │
  │                                │ SET status='approved'    │
  │                                │ WHERE id='sub_A'         │
  │                                │                          │
  │                                │<─────────────────────────┤
  │                                │ POST /reject (sub_A)     │
  │                                │                          │
  │                                │ UPDATE mobile_inbox      │
  │                                │ SET status='rejected'    │
  │                                │ WHERE id='sub_A'         │
  │                                │                          │
  │                                │ Both UPDATEs execute     │
  │                                │ (no mutual exclusion)    │
  │                                │                          │
  │                                │ Final state: 'rejected'  │
  │                                │ (whichever UPDATE last)  │
  │                                │                          │

PROBLEM:
- No mutual exclusion between approve and reject
- Whichever UPDATE executes last wins
- Non-deterministic final state
- Could lose approved tasks

SOLUTION:
- Add submission-level lock
- Acquire lock before approve/reject
- Ensure only one operation succeeds
```

---

## Race Condition #4: Sync Request Consumed Twice

```
TIMELINE: Two mobiles check sync request simultaneously

Mobile 1                         Backend                    Mobile 2
  │                                │                          │
  │ GET /sync-request              │                          │
  ├──────────────────────────────>│                          │
  │                                │ requested = 'u1' in      │
  │                                │ _sync_requested          │
  │                                │ (True)                   │
  │                                │                          │
  │                                │<─────────────────────────┤
  │                                │ GET /sync-request        │
  │                                │                          │
  │                                │ requested = 'u1' in      │
  │                                │ _sync_requested          │
  │                                │ (True)                   │
  │                                │                          │
  │                                │ Both read True!          │
  │                                │                          │
  │                                │ del _sync_requested['u1']│
  │                                │ (Mobile 1's delete)      │
  │                                │                          │
  │                                │ del _sync_requested['u1']│
  │                                │ (Mobile 2's delete)      │
  │                                │ KeyError? Or succeeds?   │
  │                                │                          │
  │ Returns: sync_requested=true   │                          │
  │ Starts uploading tasks         │                          │
  │                                │                          │
  │                                │                          │
  │                                │                          │ Returns: sync_requested=true
  │                                │                          │ Also starts uploading tasks
  │                                │                          │
  │ POST /inbox (5 tasks)          │                          │
  ├──────────────────────────────>│                          │
  │                                │                          │
  │                                │<─────────────────────────┤
  │                                │ POST /inbox (5 tasks)    │
  │                                │                          │
  │                                │ Both submissions created │
  │                                │ Both will be imported!   │
  │                                │ (Duplicates!)            │
  │                                │                          │

PROBLEM:
- Read-then-delete is not atomic
- Between read and delete, another request can read same value
- Both mobiles think they received sync request
- Both upload tasks → duplicates

SOLUTION:
- Use atomic operation with lock
- Acquire lock before read and delete
- Ensure only one mobile consumes request
```

---

## Race Condition #5: Orphaned Submissions Block Queue

```
TIMELINE: First submission never approved/rejected

Mobile A                         Backend                    Desktop
  │                                │                          │
  │ POST /inbox (5 tasks)          │                          │
  ├──────────────────────────────>│                          │
  │                                │ INSERT INTO mobile_inbox │
  │                                │ (id='sub_A', status=     │
  │                                │  'pending', created_at=  │
  │                                │  '2026-05-04T14:00:00')  │
  │                                │                          │
  │                                │                          │ GET /inbox/pending
  │                                │                          ├─────────────────>
  │                                │                          │
  │                                │                          │ Returns sub_A
  │                                │                          │
  │                                │                          │ User closes app
  │                                │                          │ (without approving)
  │                                │                          │
  │ (Later, 1 hour)                │                          │
  │                                │                          │
  │ POST /inbox (3 tasks)          │                          │
  ├──────────────────────────────>│                          │
  │                                │ INSERT INTO mobile_inbox │
  │                                │ (id='sub_B', status=     │
  │                                │  'pending', created_at=  │
  │                                │  '2026-05-04T15:00:00')  │
  │                                │                          │
  │                                │                          │ GET /inbox/pending
  │                                │                          ├─────────────────>
  │                                │                          │
  │                                │                          │ SELECT ... WHERE
  │                                │                          │ status='pending'
  │                                │                          │ ORDER BY created_at
  │                                │                          │ LIMIT 1
  │                                │                          │
  │                                │                          │ Returns sub_A
  │                                │                          │ (oldest, still pending)
  │                                │                          │
  │                                │                          │ User closes app again
  │                                │                          │ (without approving)
  │                                │                          │
  │ (Later, 2 hours)               │                          │
  │                                │                          │
  │ POST /inbox (2 tasks)          │                          │
  ├──────────────────────────────>│                          │
  │                                │ INSERT INTO mobile_inbox │
  │                                │ (id='sub_C', ...)        │
  │                                │                          │
  │                                │                          │ GET /inbox/pending
  │                                │                          ├─────────────────>
  │                                │                          │
  │                                │                          │ Still returns sub_A!
  │                                │                          │
  │                                │                          │ sub_B and sub_C
  │                                │                          │ are BLOCKED!
  │                                │                          │

PROBLEM:
- sub_A is orphaned (pending forever)
- sub_B and sub_C are blocked (can't be processed)
- No cleanup mechanism
- User can't sync new tasks

SOLUTION:
- Add timeout-based cleanup
- If submission is pending > 24 hours, auto-reject
- Or implement "processing" state to track active submissions
```

---

## Race Condition #6: Partial Import Failure

```
TIMELINE: Some tasks fail during import

Desktop                          Backend                    Database
  │                                │                          │
  │ POST /approve                  │                          │
  │ (5 tasks selected)             │                          │
  ├──────────────────────────────>│                          │
  │                                │ FOR EACH task:           │
  │                                │                          │
  │                                │ Task 1: validate ✓       │
  │                                │         create_task ✓    │
  │                                │                          │ INSERT task 1
  │                                │                          │
  │                                │ Task 2: validate ✓       │
  │                                │         create_task ✓    │
  │                                │                          │ INSERT task 2
  │                                │                          │
  │                                │ Task 3: validate ✗       │
  │                                │         (invalid data)   │
  │                                │         skip             │
  │                                │                          │
  │                                │ Task 4: validate ✓       │
  │                                │         create_task ✓    │
  │                                │                          │ INSERT task 4
  │                                │                          │
  │                                │ Task 5: validate ✓       │
  │                                │         create_task ✗    │
  │                                │         (DB error)       │
  │                                │         skip             │
  │                                │                          │
  │                                │ UPDATE mobile_inbox      │
  │                                │ SET status='approved'    │
  │                                │ (even though 2 failed!)  │
  │                                │                          │
  │ Returns:                       │                          │
  │ created_tasks: 3               │                          │
  │ skipped: [Task 3, Task 5]      │                          │
  │                                │                          │

PROBLEM:
- 3 tasks imported, 2 failed
- Submission marked as 'approved' (all-or-nothing failed)
- No way to retry Task 3 and Task 5
- User doesn't know which tasks failed
- Tasks are lost

SOLUTION:
- Option 1: Atomic all-or-nothing
  └─ If any task fails, rollback all and return error
  
- Option 2: Partial with retry queue
  └─ Store failed tasks in retry_queue table
  └─ Allow user to retry failed tasks later
  └─ Mark submission as 'partial' instead of 'approved'
```

---

## Race Condition #7: Duplicate Task Detection Missing

```
TIMELINE: Same task created on both devices

Desktop                          Mobile
  │                                │
  │ User creates:                  │
  │ "Buy groceries"                │
  │ due: 2026-05-05                │
  │                                │
  │ (Desktop has task)             │
  │                                │
  │                                │ User creates:
  │                                │ "Buy groceries"
  │                                │ due: 2026-05-05
  │                                │
  │                                │ (Mobile has task)
  │                                │
  │                                │ Syncs to desktop
  │                                │
  │ POST /approve                  │
  ├──────────────────────────────>│
  │                                │
  │                                │ Backend: create_task()
  │                                │ (NO DUPLICATE CHECK!)
  │                                │
  │ Desktop now has:               │
  │ ├─ "Buy groceries" (original)  │
  │ └─ "Buy groceries" (from sync) │
  │                                │
  │ User confused!                 │
  │ Has to manually delete one     │
  │                                │

PROBLEM:
- No duplicate detection
- Same task created twice
- User confusion
- Data duplication

SOLUTION:
- Before importing, check if task exists
- Match by: title + due_date (or title + project)
- If exists and not completed, skip or merge
```

---

## Race Condition #8: Polling Latency

```
TIMELINE: Worst-case polling latency

T0:  User clicks "Sync"
     └─ Desktop: POST /request-sync

T0.5: _sync_requested['u1'] = timestamp

T1:  Mobile just finished polling (bad timing)
     └─ Next poll in 5 seconds

T5.5: Mobile: GET /sync-request
      └─ Returns: sync_requested=true
      └─ Mobile: del _sync_requested['u1']

T5.6: Mobile starts preparing tasks (5 seconds)

T10.6: Mobile: POST /inbox (5 tasks)
       └─ Backend: INSERT INTO mobile_inbox

T10.7: Desktop just finished polling (bad timing)
       └─ Next poll in 5 seconds

T15.7: Desktop: GET /inbox/pending
       └─ Returns submission

T15.8: Desktop shows modal
       └─ User sees tasks

TOTAL LATENCY: ~15.8 seconds

WORST CASE: If timing is always bad:
├─ T0: Sync request
├─ T5: Mobile polls (misses by 0.1s)
├─ T10: Mobile polls again
├─ T10.5: Mobile starts preparing (5s)
├─ T15.5: Mobile sends tasks
├─ T20: Desktop polls (misses by 0.1s)
├─ T25: Desktop polls again
├─ T25.5: Desktop shows modal
└─ TOTAL: ~25.5 seconds (up to 90s if exponential backoff)

PROBLEM:
- Exponential backoff: 5s → 7.5s → 11.25s → 16.87s → 25.3s → 30s
- No jitter (thundering herd)
- Polling continues even after modal shown
- Battery drain on mobile

SOLUTION:
- Implement WebSocket or Server-Sent Events
- Or add jitter: interval + random(0-1000ms)
- Or use shorter initial interval: 1s instead of 5s
```

---

## Summary: Race Condition Impact Matrix

```
┌─────────────────────────────────────────────────────────────┐
│ Race Condition Impact Analysis                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ RC#1: Lost Sync Request                                     │
│ ├─ Data Loss: ✓ (sync request lost)                         │
│ ├─ Duplicate Data: ✗                                        │
│ ├─ Inconsistent State: ✓                                    │
│ ├─ User Impact: High (confusing UX)                         │
│ └─ Frequency: Medium (only on app crash)                    │
│                                                              │
│ RC#2: Concurrent Submissions                                │
│ ├─ Data Loss: ✗                                             │
│ ├─ Duplicate Data: ✗                                        │
│ ├─ Inconsistent State: ✓ (wrong order)                      │
│ ├─ User Impact: Medium (wrong order of processing)          │
│ └─ Frequency: High (every multi-device sync)                │
│                                                              │
│ RC#3: Concurrent Approve/Reject                             │
│ ├─ Data Loss: ✓ (approved tasks lost)                       │
│ ├─ Duplicate Data: ✗                                        │
│ ├─ Inconsistent State: ✓                                    │
│ ├─ User Impact: High (tasks disappear)                      │
│ └─ Frequency: Low (requires simultaneous clicks)            │
│                                                              │
│ RC#4: Sync Request Consumed Twice                           │
│ ├─ Data Loss: ✗                                             │
│ ├─ Duplicate Data: ✓ (duplicate imports)                    │
│ ├─ Inconsistent State: ✓                                    │
│ ├─ User Impact: High (duplicate tasks)                      │
│ └─ Frequency: Medium (multi-device scenario)                │
│                                                              │
│ RC#5: Orphaned Submissions                                  │
│ ├─ Data Loss: ✓ (new submissions blocked)                   │
│ ├─ Duplicate Data: ✗                                        │
│ ├─ Inconsistent State: ✓                                    │
│ ├─ User Impact: High (can't sync)                           │
│ └─ Frequency: Medium (if user closes app)                   │
│                                                              │
│ RC#6: Partial Import Failure                                │
│ ├─ Data Loss: ✓ (failed tasks lost)                         │
│ ├─ Duplicate Data: ✗                                        │
│ ├─ Inconsistent State: ✓                                    │
│ ├─ User Impact: High (silent data loss)                     │
│ └─ Frequency: Medium (on validation errors)                 │
│                                                              │
│ RC#7: Duplicate Detection Missing                           │
│ ├─ Data Loss: ✗                                             │
│ ├─ Duplicate Data: ✓ (duplicate tasks)                      │
│ ├─ Inconsistent State: ✗                                    │
│ ├─ User Impact: Medium (confusing duplicates)               │
│ └─ Frequency: High (common scenario)                        │
│                                                              │
│ RC#8: Polling Latency                                       │
│ ├─ Data Loss: ✗                                             │
│ ├─ Duplicate Data: ✗                                        │
│ ├─ Inconsistent State: ✗                                    │
│ ├─ User Impact: Low (just slow)                             │
│ └─ Frequency: Always (every sync)                           │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Recommended Fix Order

1. **RC#4: Sync Request Consumed Twice** (1 hour)
   - Add lock to read-delete operation
   - Prevents duplicate imports

2. **RC#3: Concurrent Approve/Reject** (2 hours)
   - Add submission-level locks
   - Prevents lost approved tasks

3. **RC#1: Lost Sync Request** (4 hours)
   - Move to database with TTL
   - Prevents data loss on restart

4. **RC#5: Orphaned Submissions** (2 hours)
   - Add cleanup job
   - Prevents sync blocking

5. **RC#2: Concurrent Submissions** (4 hours)
   - Add sequence numbers
   - Ensures correct ordering

6. **RC#6: Partial Import Failure** (8 hours)
   - Add retry queue
   - Prevents silent data loss

7. **RC#7: Duplicate Detection** (4 hours)
   - Check before importing
   - Prevents duplicate tasks

8. **RC#8: Polling Latency** (16 hours)
   - Implement WebSocket
   - Improves UX and battery

**Total Effort: 2-3 weeks for all fixes**
