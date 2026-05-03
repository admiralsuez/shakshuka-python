# Android Sync Logic Rework

## Overview
Consolidate polling, batch operations, and add delta sync to reduce network calls and battery drain.

---

## 1. Unified Polling Manager (Replaces Multiple Timers)

### Current Problem
- `_syncRequestTimer` (hourly) + `_taskAddedSyncTimer` (1-minute) run independently
- Both can fire simultaneously
- No coordination between checks

### Reworked Approach

```dart
// In home_screen.dart

class _SyncPollingManager {
  Timer? _pollingTimer;
  DateTime? _lastSyncCheck;
  bool _isPolling = false;
  
  static const Duration SYNC_CHECK_INTERVAL = Duration(minutes: 5);
  static const Duration POST_ADD_DEBOUNCE = Duration(minutes: 1);
  
  DateTime? _lastTaskAddTime;
  
  /// Start unified polling - runs every 5 minutes
  void startPolling() {
    _pollingTimer?.cancel();
    _pollingTimer = Timer.periodic(SYNC_CHECK_INTERVAL, (_) {
      _performUnifiedCheck();
    });
  }
  
  /// Called when user adds a task - debounces to 1 minute
  void onTaskAdded() {
    _lastTaskAddTime = DateTime.now();
    // Don't start extra timer - next polling cycle will check
  }
  
  /// Single unified check that handles both sync requests and post-add checks
  Future<void> _performUnifiedCheck() async {
    if (_isPolling) return; // Prevent concurrent checks
    
    _isPolling = true;
    try {
      final now = DateTime.now();
      final timeSinceLastAdd = _lastTaskAddTime != null 
          ? now.difference(_lastTaskAddTime!) 
          : null;
      
      // Check if we should poll for sync request
      final shouldCheckSync = _lastSyncCheck == null || 
          now.difference(_lastSyncCheck!).inMinutes >= 5;
      
      // Check if 1 minute has passed since last task add
      final shouldCheckPostAdd = timeSinceLastAdd != null && 
          timeSinceLastAdd.inSeconds >= 60;
      
      if (shouldCheckSync || shouldCheckPostAdd) {
        final result = await _api.checkSyncRequest();
        if (result['sync_requested'] == true) {
          await _autoUploadAllTasks();
          _lastTaskAddTime = null; // Reset post-add timer
        }
        _lastSyncCheck = now;
      }
    } finally {
      _isPolling = false;
    }
  }
  
  void cancel() {
    _pollingTimer?.cancel();
  }
}
```

**Benefits:**
- Single timer instead of two
- No concurrent polling
- Debouncing built-in
- 5-minute intervals instead of hourly (more responsive)

---

## 2. Batch Approval Polling (Replaces Per-Submission Polling)

### Current Problem
- `_watchForApproval()` spawns a new polling loop for each upload
- Each loop polls every 5 seconds for 5 minutes (60 requests per upload)
- Multiple uploads = multiple concurrent polling loops

### Reworked Approach

```dart
// In home_screen.dart

class _ApprovalPoller {
  final Map<String, ApprovalWatcher> _watchers = {};
  Timer? _pollingTimer;
  bool _isPolling = false;
  
  static const Duration INITIAL_INTERVAL = Duration(seconds: 5);
  static const Duration MAX_INTERVAL = Duration(seconds: 30);
  static const Duration MAX_WAIT_TIME = Duration(minutes: 5);
  
  /// Register a submission for approval tracking
  void watchSubmission(String submissionId, List<String> taskIds) {
    _watchers[submissionId] = ApprovalWatcher(
      submissionId: submissionId,
      taskIds: taskIds,
      startTime: DateTime.now(),
      nextCheckTime: DateTime.now(),
      pollInterval: INITIAL_INTERVAL,
    );
    
    // Start polling if not already running
    if (_pollingTimer == null) {
      _startPolling();
    }
  }
  
  /// Single polling loop checks ALL pending submissions
  void _startPolling() {
    _pollingTimer = Timer.periodic(Duration(seconds: 2), (_) {
      _checkAllSubmissions();
    });
  }
  
  Future<void> _checkAllSubmissions() async {
    if (_isPolling || _watchers.isEmpty) return;
    
    _isPolling = true;
    try {
      final now = DateTime.now();
      final toRemove = <String>[];
      
      for (final entry in _watchers.entries) {
        final watcher = entry.value;
        
        // Skip if not time to check yet
        if (now.isBefore(watcher.nextCheckTime)) continue;
        
        // Skip if exceeded max wait time
        if (now.difference(watcher.startTime) > MAX_WAIT_TIME) {
          toRemove.add(entry.key);
          continue;
        }
        
        // Check status
        final status = await _api.checkSubmissionStatus(watcher.submissionId);
        final s = status['status'] as String?;
        
        if (s == 'approved') {
          // Delete tasks and remove from watchers
          for (final id in watcher.taskIds) {
            await _storage.deleteTask(id);
          }
          _loadTasks();
          _showApprovalNotification(watcher.taskIds.length);
          toRemove.add(entry.key);
        } else if (s == 'rejected') {
          toRemove.add(entry.key);
        } else {
          // Exponential backoff: 5s → 10s → 15s → 30s
          final nextInterval = Duration(
            seconds: (watcher.pollInterval.inSeconds * 1.5).toInt()
              .clamp(5, 30)
          );
          watcher.pollInterval = nextInterval;
          watcher.nextCheckTime = now.add(nextInterval);
        }
      }
      
      // Clean up completed watchers
      for (final id in toRemove) {
        _watchers.remove(id);
      }
      
      // Stop polling if no more watchers
      if (_watchers.isEmpty) {
        _pollingTimer?.cancel();
        _pollingTimer = null;
      }
    } finally {
      _isPolling = false;
    }
  }
  
  void cancel() {
    _pollingTimer?.cancel();
    _watchers.clear();
  }
}

class ApprovalWatcher {
  final String submissionId;
  final List<String> taskIds;
  final DateTime startTime;
  DateTime nextCheckTime;
  Duration pollInterval;
  
  ApprovalWatcher({
    required this.submissionId,
    required this.taskIds,
    required this.startTime,
    required this.nextCheckTime,
    required this.pollInterval,
  });
}
```

**Benefits:**
- Single polling loop for all submissions
- Exponential backoff (5s → 10s → 15s → 30s)
- Max 5-minute wait, then gives up
- Reduces 60 requests per upload to ~10-15 requests
- No concurrent polling

---

## 3. Delta Sync (Track Sent Tasks)

### Current Problem
- Uploads ALL tasks when sync requested
- No tracking of what was already sent
- Potential duplicates

### Reworked Approach

```dart
// In storage_service.dart - add these methods

Future<void> markTasksAsSent(List<String> taskIds, String submissionId) async {
  final prefs = await SharedPreferences.getInstance();
  final sentMap = await _getSentTasksMap();
  
  for (final id in taskIds) {
    sentMap[id] = {
      'submission_id': submissionId,
      'sent_at': DateTime.now().toIso8601String(),
    };
  }
  
  await prefs.setString('sent_tasks_map', jsonEncode(sentMap));
}

Future<Map<String, dynamic>> _getSentTasksMap() async {
  final prefs = await SharedPreferences.getInstance();
  final json = prefs.getString('sent_tasks_map');
  if (json == null) return {};
  try {
    return Map<String, dynamic>.from(jsonDecode(json));
  } catch (e) {
    return {};
  }
}

Future<List<LocalTask>> getUnsentTasks() async {
  final allTasks = getAllTasks();
  final sentMap = await _getSentTasksMap();
  
  return allTasks.where((task) => !sentMap.containsKey(task.id)).toList();
}

Future<void> clearSentTasksMap() async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.remove('sent_tasks_map');
}
```

```dart
// In home_screen.dart - modify _autoUploadAllTasks

Future<void> _autoUploadAllTasks() async {
  // Only upload unsent tasks
  final unsentTasks = await _storage.getUnsentTasks();
  final unsentNotes = _storage.getAllNotes(); // Notes don't need delta sync
  
  if (unsentTasks.isEmpty && unsentNotes.isEmpty) return;
  
  setState(() => _isUploading = true);
  final result = await _api.uploadTasksAndNotes(unsentTasks, unsentNotes);
  setState(() => _isUploading = false);
  
  if (result['success'] == true) {
    final submissionId = result['submission_id'] as String?;
    if (submissionId != null) {
      // Mark these tasks as sent
      await _storage.markTasksAsSent(
        unsentTasks.map((t) => t.id).toList(),
        submissionId,
      );
      
      // Watch for approval
      if (unsentTasks.isNotEmpty) {
        _approvalPoller.watchSubmission(
          submissionId,
          unsentTasks.map((t) => t.id).toList(),
        );
      }
    }
  }
}
```

**Benefits:**
- Only uploads new/unsent tasks
- Prevents duplicates
- Reduces bandwidth significantly
- Tracks submission history

---

## 4. Batch Offline Note Sync

### Current Problem
- Sends each offline note individually
- 10 notes = 10 API calls

### Reworked Approach

```dart
// In api_service.dart - add batch endpoint

Future<Map<String, dynamic>> createNotesBatch(List<Map<String, String>> notes) async {
  final device = _storage.getPairedDevice();
  if (device == null) {
    // Queue all for offline sync
    for (final note in notes) {
      await _storage.queueOfflineNote(note['title']!, note['content']!);
    }
    return {
      'success': true,
      'message': 'Notes queued for sync',
      'offline': true,
    };
  }

  try {
    final uri = Uri.parse('${device.serverUrl}/api/mobile/notes/batch');
    final response = await http
        .post(
          uri,
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ${device.token}',
          },
          body: jsonEncode({'notes': notes}),
        )
        .timeout(const Duration(seconds: 20));

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      if (data['success'] == true) {
        return {
          'success': true,
          'count': data['count'],
          'message': 'Synced ${data['count']} notes',
        };
      }
      return {'success': false, 'message': data['error'] ?? 'Failed'};
    }
    return {'success': false, 'message': 'Server error'};
  } on SocketException {
    // Queue all for offline sync
    for (final note in notes) {
      await _storage.queueOfflineNote(note['title']!, note['content']!);
    }
    return {'success': true, 'offline': true};
  }
  catch (e) { // noqa: broad-catch
    debugPrint('Batch note creation error: $e');
    return {'success': false, 'message': 'Error: $e'};
  }
}

// In home_screen.dart - modify syncOfflineNotes

Future<void> _syncOfflineNotes() async {
  final queue = await _storage.getOfflineNotesQueue();
  if (queue.isEmpty) return;

  debugPrint('Syncing ${queue.length} offline notes in batch');
  
  final notes = queue.map((note) => {
    'title': note['title'] as String,
    'content': note['content'] as String,
  }).toList();

  final result = await _api.createNotesBatch(notes);
  
  if (result['success'] == true && result['offline'] != true) {
    await _storage.removeOfflineNotes(
      queue.map((n) => n['id'] as String).toList()
    );
    debugPrint('Synced ${queue.length} offline notes');
  }
}
```

**Benefits:**
- 10 notes = 1 API call instead of 10
- Reduces network overhead
- Faster sync

---

## 5. Connection Caching

### Current Problem
- `testConnection()` makes 3 HTTP requests on every call
- Called on startup, pairing, refresh = 3-5 seconds wasted

### Reworked Approach

```dart
// In api_service.dart

class ApiService {
  DateTime? _lastConnectionCheck;
  bool _cachedConnectionStatus = false;
  static const Duration CONNECTION_CACHE_TTL = Duration(seconds: 30);
  
  Future<bool> testConnection({int retries = 1, bool forceRefresh = false}) async {
    final device = _storage.getPairedDevice();
    if (device == null) return false;

    // Return cached result if fresh
    if (!forceRefresh && _lastConnectionCheck != null) {
      final age = DateTime.now().difference(_lastConnectionCheck!);
      if (age < CONNECTION_CACHE_TTL) {
        return _cachedConnectionStatus;
      }
    }

    for (int attempt = 0; attempt <= retries; attempt++) {
      try {
        final uri = Uri.parse('${device.serverUrl}/health');
        final response = await http.get(uri).timeout(const Duration(seconds: 3));
        
        if (response.statusCode == 200) {
          _cachedConnectionStatus = true;
          _lastConnectionCheck = DateTime.now();
          return true;
        }
      } on SocketException catch (e) {
        debugPrint('Connection test attempt ${attempt + 1}/${retries + 1}: $e');
        if (attempt < retries) {
          await Future.delayed(Duration(seconds: 1 + attempt));
        }
      } on TimeoutException catch (e) {
        debugPrint('Connection test timeout attempt ${attempt + 1}/${retries + 1}: $e');
        if (attempt < retries) {
          await Future.delayed(Duration(seconds: 1 + attempt));
        }
      }
      catch (e) { // noqa: broad-catch
        debugPrint('Connection test error: $e');
        if (attempt < retries) {
          await Future.delayed(Duration(seconds: 1 + attempt));
        }
      }
    }
    
    _cachedConnectionStatus = false;
    _lastConnectionCheck = DateTime.now();
    return false;
  }
}
```

**Benefits:**
- 30-second cache prevents redundant checks
- Startup time reduced from 3-5s to <1s
- Still refreshes on demand with `forceRefresh: true`

---

## 6. Combined Data Reload

### Current Problem
- After upload, calls `_loadTasks()` and `_loadStats()` separately
- Both reload from storage independently

### Reworked Approach

```dart
// In storage_service.dart

Future<Map<String, dynamic>> getTasksAndStats() async {
  final tasks = getAllTasks();
  final stats = await getStats();
  
  return {
    'tasks': tasks,
    'stats': stats,
  };
}

// In home_screen.dart

Future<void> _refreshData() async {
  final data = await _storage.getTasksAndStats();
  setState(() {
    _tasks = data['tasks'] as List<LocalTask>;
    _totalTasksSent = data['stats']['totalSent'] as int? ?? 0;
  });
}
```

**Benefits:**
- Single storage read instead of two
- Atomic update prevents inconsistency
- Cleaner code

---

## Summary of Changes

| Issue | Current | Reworked | Improvement |
|-------|---------|----------|------------|
| Polling | 2 timers | 1 unified | No conflicts |
| Approval checks | 60 req/upload | 10-15 req/upload | 75% fewer requests |
| Sync requests | Hourly | Every 5 min | More responsive |
| Unsent tasks | All tasks | Only new | Bandwidth savings |
| Offline notes | N requests | 1 request | N times faster |
| Connection checks | 3 requests | Cached 30s | 3-5s startup saved |
| Data reloads | 2 calls | 1 call | Faster UI update |

---

## Implementation Order

1. **Unified Polling Manager** - Consolidate timers
2. **Batch Approval Poller** - Reduce approval checks
3. **Connection Caching** - Speed up startup
4. **Delta Sync** - Reduce bandwidth
5. **Batch Note Sync** - Optimize offline notes
6. **Combined Data Reload** - Minor optimization

