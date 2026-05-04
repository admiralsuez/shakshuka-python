# Sync Logic Issues - Quick Reference

## 🔴 Critical Problems

### 1. **In-Memory Sync State (Data Loss Risk)**
- **File:** `src/routes/mobile_routes.py:28`
- **Issue:** `_sync_requested` dict loses all data on app restart
- **Fix:** Move to database with TTL
- **Impact:** User presses Sync → app crashes → sync request lost

### 2. **Polling Architecture (Inefficient)**
- **File:** `assets/static/js/app/companion-sync.js:95-109`
- **Issue:** Constant polling every 5-30 seconds, up to 90 seconds latency
- **Fix:** Implement WebSocket or Server-Sent Events
- **Impact:** High latency, battery drain, wasted bandwidth

### 3. **No Sync Request Cleanup (Memory Leak)**
- **File:** `src/routes/mobile_routes.py:576-602`
- **Issue:** Sync requests never expire from memory
- **Fix:** Add TTL-based cleanup (5 min expiry)
- **Impact:** Memory accumulates over time

---

## 🟡 Major Problems

### 4. **No Acknowledgment for Sync Requests**
- **Issue:** Desktop sends request, mobile consumes it, no retry if missed
- **Fix:** Implement acknowledgment handshake
- **Impact:** Sync can silently fail

### 5. **Concurrent Check Guard Issues**
- **File:** `assets/static/js/app/companion-sync.js:42`
- **Issue:** `_syncCheckInProgress` flag can get stuck if async hangs
- **Fix:** Add timeout-based guard (30s max)
- **Impact:** Sync can hang forever

### 6. **No Sync History/Persistence**
- **Issue:** Can't see what was synced or when
- **Fix:** Add sync log table with timestamps
- **Impact:** Poor debugging, no audit trail

---

## 🟠 Minor Problems

### 7. **Hardcoded Polling Intervals**
- **Issue:** 2-hour auto-sync, 5s→30s backoff hardcoded
- **Fix:** Load from settings
- **Impact:** Can't customize without code change

### 8. **No Duplicate Detection**
- **Issue:** Same task created on both devices = 2 imports
- **Fix:** Check for duplicates by title + due_date
- **Impact:** Duplicate tasks in system

### 9. **Poor Error Messages**
- **Issue:** Failed imports don't explain why
- **Fix:** Return detailed error per task
- **Impact:** User confusion on failures

### 10. **No Rate Limiting**
- **Issue:** Mobile can spam `/api/mobile/inbox`
- **Fix:** Add rate limit (10/min per device)
- **Impact:** Potential DoS vulnerability

---

## Quick Fix Priority

**Do First (1 day):**
1. Move `_sync_requested` to database
2. Add sync request cleanup job
3. Add timeout guard for concurrent checks

**Do Next (3 days):**
4. Implement sync acknowledgment
5. Add sync history logging
6. Improve error messages

**Do Later (1 week):**
7. Replace polling with WebSocket
8. Add duplicate detection
9. Add rate limiting
10. Make intervals configurable

---

## Code Locations

| Issue | File | Lines |
|-------|------|-------|
| In-memory state | `src/routes/mobile_routes.py` | 28, 576-602 |
| Polling logic | `assets/static/js/app/companion-sync.js` | 42-109, 151-219 |
| Concurrent guard | `assets/static/js/app/companion-sync.js` | 42, 151-152 |
| Import logic | `src/routes/mobile_routes.py` | 405-519 |
| Sync request | `src/routes/mobile_routes.py` | 576-602 |

---

## Testing Checklist

- [ ] Sync persists after app restart
- [ ] Sync request times out after 5 minutes
- [ ] Mobile receives sync request within 5 seconds
- [ ] Concurrent syncs don't cause race conditions
- [ ] Failed imports show detailed errors
- [ ] Duplicate tasks are detected
- [ ] Sync history is logged
- [ ] Rate limiting prevents spam
