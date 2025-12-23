import 'package:hive_flutter/hive_flutter.dart';
import '../models/task.dart';
import '../models/paired_device.dart';

class StorageService {
  static final StorageService _instance = StorageService._internal();
  factory StorageService() => _instance;
  StorageService._internal();

  Box<LocalTask> get _taskBox => Hive.box<LocalTask>('tasks');
  Box<PairedDevice> get _deviceBox => Hive.box<PairedDevice>('paired_device');

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

  bool get isPaired => _deviceBox.isNotEmpty;
}
