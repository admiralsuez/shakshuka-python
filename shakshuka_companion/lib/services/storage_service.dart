import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/task.dart';
import '../models/note.dart';
import '../models/paired_device.dart';

class StorageService {
  static final StorageService _instance = StorageService._internal();
  factory StorageService() => _instance;
  StorageService._internal();

  Box<LocalTask> get _taskBox => Hive.box<LocalTask>('tasks');
  Box<LocalNote> get _noteBox => Hive.box<LocalNote>('notes');
  Box<PairedDevice> get _deviceBox => Hive.box<PairedDevice>('paired_device');

  // Stats tracking
  Future<Map<String, int>> getStats() async {
    final prefs = await SharedPreferences.getInstance();
    return {
      'totalSent': prefs.getInt('total_tasks_sent') ?? 0,
      'totalCreated': prefs.getInt('total_tasks_created') ?? 0,
    };
  }

  // Theme preference (mirrors desktop theme names where possible)
  Future<String> getTheme() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('app_theme') ?? 'orange';
  }

  Future<void> setTheme(String theme) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('app_theme', theme);
  }

  Future<void> incrementTasksSent(int count) async {
    final prefs = await SharedPreferences.getInstance();
    final current = prefs.getInt('total_tasks_sent') ?? 0;
    await prefs.setInt('total_tasks_sent', current + count);
  }

  Future<void> incrementTasksCreated() async {
    final prefs = await SharedPreferences.getInstance();
    final current = prefs.getInt('total_tasks_created') ?? 0;
    await prefs.setInt('total_tasks_created', current + 1);
  }

  // Sent tasks history
  Future<void> addSentTasksHistory(List<Map<String, dynamic>> tasks, String? submissionId) async {
    final prefs = await SharedPreferences.getInstance();
    final history = await getSentTasksHistory();
    
    final entry = {
      'timestamp': DateTime.now().toIso8601String(),
      'submission_id': submissionId,
      'status': 'pending', // pending, approved, rejected
      'tasks': tasks.map((t) => {'title': t['title'] ?? 'Untitled', 'duration': t['duration']}).toList(),
    };
    history.insert(0, entry);
    
    // Keep only last 50 entries
    if (history.length > 50) {
      history.removeRange(50, history.length);
    }
    
    await prefs.setString('sent_tasks_history', jsonEncode(history));
  }

  Future<void> updateHistoryStatus(String submissionId, String status) async {
    final prefs = await SharedPreferences.getInstance();
    final history = await getSentTasksHistory();
    
    for (var entry in history) {
      if (entry['submission_id'] == submissionId) {
        entry['status'] = status;
        // For backward compatibility with UI
        entry['accepted'] = status == 'approved';
        break;
      }
    }
    
    await prefs.setString('sent_tasks_history', jsonEncode(history));
  }

  Future<List<Map<String, dynamic>>> getSentTasksHistory() async {
    final prefs = await SharedPreferences.getInstance();
    final historyJson = prefs.getString('sent_tasks_history');
    if (historyJson == null || historyJson.isEmpty) return [];
    try {
      final list = jsonDecode(historyJson) as List;
      return list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    }
    catch (e) { // noqa: broad-catch
      debugPrint('Failed to parse sent tasks history: $e');
      return [];
    }
  }

  // Delta sync - track which tasks have been sent to prevent duplicates
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
    debugPrint('Marked ${taskIds.length} tasks as sent');
  }

  Future<Map<String, dynamic>> _getSentTasksMap() async {
    final prefs = await SharedPreferences.getInstance();
    final json = prefs.getString('sent_tasks_map');
    if (json == null) return {};
    try {
      return Map<String, dynamic>.from(jsonDecode(json));
    }
    catch (e) { // noqa: broad-catch
      debugPrint('Failed to parse sent tasks map: $e');
      return {};
    }
  }

  Future<List<LocalTask>> getUnsentTasks() async {
    final allTasks = getAllTasks();
    final sentMap = await _getSentTasksMap();
    
    final unsent = allTasks.where((task) => !sentMap.containsKey(task.id)).toList();
    debugPrint('Found ${unsent.length} unsent tasks out of ${allTasks.length}');
    return unsent;
  }

  Future<void> clearSentTasksMap() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('sent_tasks_map');
  }

  // Tasks
  List<LocalTask> getAllTasks() {
    return _taskBox.values.toList()
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
  }

  Future<void> addTask(LocalTask task) async {
    await _taskBox.put(task.id, task);
  }

  Future<void> deleteTask(String id) async {
    await _taskBox.delete(id);
  }

  Future<void> updateTask(LocalTask task) async {
    await _taskBox.put(task.id, task);
  }

  Future<void> clearAllTasks() async {
    await _taskBox.clear();
  }

  int get taskCount => _taskBox.length;

  // Local Notes (to be sent to PC)
  List<LocalNote> getAllNotes() {
    return _noteBox.values.toList()
      ..sort((a, b) => b.createdAt.compareTo(a.createdAt));
  }

  Future<void> addNote(LocalNote note) async {
    await _noteBox.put(note.id, note);
  }

  Future<void> deleteNote(String id) async {
    await _noteBox.delete(id);
  }

  Future<void> updateNote(LocalNote note) async {
    await _noteBox.put(note.id, note);
  }

  Future<void> clearAllNotes() async {
    await _noteBox.clear();
  }

  int get noteCount => _noteBox.length;

  // Paired Device
  PairedDevice? getPairedDevice() {
    if (_deviceBox.isEmpty) return null;
    return _deviceBox.getAt(0);
  }

  Future<void> savePairedDevice(PairedDevice device) async {
    await _deviceBox.clear();
    await _deviceBox.add(device);
  }

  Future<void> unpairDevice() async {
    await _deviceBox.clear();
  }

  // Alias for unpairDevice - used when device is unpaired from desktop
  Future<void> clearPairing() async {
    await _deviceBox.clear();
  }

  bool get isPaired => _deviceBox.isNotEmpty;

  // Current tasks caching for offline viewing
  Future<void> cacheCurrentTasks(List<dynamic> tasks) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('cached_current_tasks', jsonEncode(tasks));
      await prefs.setString('cached_tasks_timestamp', DateTime.now().toIso8601String());
      debugPrint('Cached ${tasks.length} current tasks');
    }
    catch (e) { // noqa: broad-catch
      debugPrint('Failed to cache current tasks: $e');
    }
  }

  Future<List<Map<String, dynamic>>> getCachedCurrentTasks() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cachedJson = prefs.getString('cached_current_tasks');
      if (cachedJson == null || cachedJson.isEmpty) return [];
      
      final list = jsonDecode(cachedJson) as List;
      return list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    }
    catch (e) { // noqa: broad-catch
      debugPrint('Failed to load cached tasks: $e');
      return [];
    }
  }

  Future<String?> getCachedTasksTimestamp() async {
    final prefs = await SharedPreferences.getInstance();
    return prefs.getString('cached_tasks_timestamp');
  }

  // Notes caching for offline viewing
  Future<void> cacheNotes(List<dynamic> notes) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('cached_notes', jsonEncode(notes));
      await prefs.setString('cached_notes_timestamp', DateTime.now().toIso8601String());
      debugPrint('Cached ${notes.length} notes');
    }
    catch (e) { // noqa: broad-catch
      debugPrint('Failed to cache notes: $e');
    }
  }

  Future<List<Map<String, dynamic>>> getCachedNotes() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final cachedJson = prefs.getString('cached_notes');
      if (cachedJson == null || cachedJson.isEmpty) return [];
      
      final list = jsonDecode(cachedJson) as List;
      return list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    }
    catch (e) { // noqa: broad-catch
      debugPrint('Failed to load cached notes: $e');
      return [];
    }
  }

  // Offline notes queue
  Future<void> queueOfflineNote(String title, String content) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final queue = await getOfflineNotesQueue();
      
      final note = {
        'id': DateTime.now().millisecondsSinceEpoch.toString(),
        'title': title,
        'content': content,
        'created_at': DateTime.now().toIso8601String(),
      };
      
      queue.add(note);
      await prefs.setString('offline_notes_queue', jsonEncode(queue));
      debugPrint('Queued offline note: $title');
    }
    catch (e) { // noqa: broad-catch
      debugPrint('Failed to queue offline note: $e');
    }
  }

  Future<List<Map<String, dynamic>>> getOfflineNotesQueue() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final queueJson = prefs.getString('offline_notes_queue');
      if (queueJson == null || queueJson.isEmpty) return [];
      
      final list = jsonDecode(queueJson) as List;
      return list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    }
    catch (e) { // noqa: broad-catch
      debugPrint('Failed to load offline notes queue: $e');
      return [];
    }
  }

  Future<void> removeOfflineNotes(List<String> ids) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final queue = await getOfflineNotesQueue();
      
      final updated = queue.where((note) => !ids.contains(note['id'])).toList();
      await prefs.setString('offline_notes_queue', jsonEncode(updated));
      debugPrint('Removed ${ids.length} synced notes from queue');
    }
    catch (e) { // noqa: broad-catch
      debugPrint('Failed to remove synced notes: $e');
    }
  }
}
