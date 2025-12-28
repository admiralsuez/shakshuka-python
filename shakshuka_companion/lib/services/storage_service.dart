import 'dart:convert';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../models/task.dart';
import '../models/paired_device.dart';

class StorageService {
  static final StorageService _instance = StorageService._internal();
  factory StorageService() => _instance;
  StorageService._internal();

  Box<LocalTask> get _taskBox => Hive.box<LocalTask>('tasks');
  Box<PairedDevice> get _deviceBox => Hive.box<PairedDevice>('paired_device');

  // Stats tracking
  Future<Map<String, int>> getStats() async {
    final prefs = await SharedPreferences.getInstance();
    return {
      'totalSent': prefs.getInt('total_tasks_sent') ?? 0,
      'totalCreated': prefs.getInt('total_tasks_created') ?? 0,
    };
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
    } catch (_) {
      return [];
    }
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
}
