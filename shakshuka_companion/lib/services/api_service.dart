import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import '../models/task.dart';
import '../models/note.dart';
import '../models/paired_device.dart';
import 'storage_service.dart';

class ApiService {
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  final StorageService _storage = StorageService();
  
  // Connection caching - avoid redundant health checks
  DateTime? _lastConnectionCheck;
  bool _cachedConnectionStatus = false;
  static const Duration CONNECTION_CACHE_TTL = Duration(seconds: 30);

  Future<Map<String, dynamic>> pairWithServer({
    required String serverUrl,
    required String code,
    required String deviceName,
  }) async {
    try {
      final uri = Uri.parse('$serverUrl/api/mobile/pair');
      final deviceId = DateTime.now().millisecondsSinceEpoch.toString();

      final response = await http
          .post(
            uri,
            headers: {'Content-Type': 'application/json'},
            body: jsonEncode({
              'code': code,
              'device_id': deviceId,
              'device_name': deviceName,
            }),
          )
          .timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true && data['token'] != null) {
          final device = PairedDevice(
            serverUrl: serverUrl,
            token: data['token'],
            deviceName: deviceName,
          );
          await _storage.savePairedDevice(device);
          
          // Auto-sync any pending tasks/notes after successful pairing
          debugPrint('Pairing successful, attempting to sync pending tasks/notes');
          await Future.delayed(const Duration(milliseconds: 500));
          final tasks = _storage.getAllTasks();
          final notes = _storage.getAllNotes();
          if (tasks.isNotEmpty || notes.isNotEmpty) {
            debugPrint('Found ${tasks.length} tasks and ${notes.length} notes to sync after pairing');
            final uploadResult = await uploadTasksAndNotes(tasks, notes);
            if (uploadResult['success'] == true) {
              debugPrint('Successfully synced ${tasks.length} tasks and ${notes.length} notes after pairing');
              debugPrint('Note: Tasks/notes are NOT auto-deleted. User must manually delete them from phone after desktop accepts.');
            } else {
              debugPrint('Failed to sync tasks/notes after pairing: ${uploadResult['message']}');
            }
          } else {
            debugPrint('No tasks or notes to sync after pairing');
          }
          
          return {'success': true, 'message': 'Paired successfully!', 'synced': tasks.isNotEmpty || notes.isNotEmpty};
        }
        return {
          'success': false,
          'message': data['error'] ?? 'Pairing failed'
        };
      } else {
        final data = jsonDecode(response.body);
        return {
          'success': false,
          'message': data['error'] ?? 'Server error: ${response.statusCode}'
        };
      }
    } on SocketException {
      return {'success': false, 'message': 'Cannot connect to server'};
    } on http.ClientException {
      return {'success': false, 'message': 'Connection failed'};
    } on TimeoutException {
      return {'success': false, 'message': 'Connection timeout'};
    }
    catch (e) { // noqa: broad-catch
      debugPrint('Pairing error: $e');
      return {'success': false, 'message': 'Error: $e'};
    }
  }

  Future<Map<String, dynamic>> uploadTasksAndNotes(
    List<LocalTask> tasks,
    List<LocalNote> notes, {
    int retries = 1,
  }) async {
    final device = _storage.getPairedDevice();
    if (device == null) {
      return {'success': false, 'message': 'Not paired with any PC'};
    }

    if (tasks.isEmpty && notes.isEmpty) {
      return {'success': false, 'message': 'Nothing to upload'};
    }

    for (int attempt = 0; attempt <= retries; attempt++) {
      try {
        final uri = Uri.parse('${device.serverUrl}/api/mobile/inbox');
        final response = await http
            .post(
              uri,
              headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Bearer ${device.token}',
              },
              body: jsonEncode({
                'tasks': tasks.map((t) => t.toJson()).toList(),
                'notes': notes.map((n) => n.toJson()).toList(),
              }),
            )
            .timeout(const Duration(seconds: 15));

        if (response.statusCode == 200) {
          final data = jsonDecode(response.body);
          if (data['success'] == true) {
            final tasksCount = data['tasks_count'] ?? tasks.length;
            final notesCount = data['notes_count'] ?? notes.length;
            String message = '';
            if (tasksCount > 0 && notesCount > 0) {
              message = 'Uploaded $tasksCount task(s) and $notesCount note(s) to PC inbox!';
            } else if (tasksCount > 0) {
              message = 'Uploaded $tasksCount task(s) to PC inbox!';
            } else {
              message = 'Uploaded $notesCount note(s) to PC inbox!';
            }
            return {
              'success': true,
              'message': message,
              'submission_id': data['submission_id'],
              'tasks_count': tasksCount,
              'notes_count': notesCount,
            };
          }
          return {
            'success': false,
            'message': data['error'] ?? 'Upload failed'
          };
        } else if (response.statusCode == 401) {
          // Device was unpaired from desktop - clear local pairing
          await _storage.clearPairing();
        return {
            'success': false,
            'message': 'Device was unpaired from PC. Please pair again.',
            'unpaired': true,
          };
        } else {
          return {
            'success': false,
            'message': 'Server error: ${response.statusCode}'
          };
        }
      }
      on SocketException catch (e) {
        debugPrint('Upload attempt ${attempt + 1}/${retries + 1}: SocketException - $e');
        if (attempt < retries) {
          await Future.delayed(Duration(seconds: 2 + attempt));
          continue;
        }
        return {'success': false, 'message': 'Cannot connect to PC. Check network connection.'};
      }
      on http.ClientException catch (e) {
        debugPrint('Upload attempt ${attempt + 1}/${retries + 1}: ClientException - $e');
        if (attempt < retries) {
          await Future.delayed(Duration(seconds: 2 + attempt));
          continue;
        }
        return {'success': false, 'message': 'Connection failed. Try again.'};
      }
      on TimeoutException catch (e) {
        debugPrint('Upload attempt ${attempt + 1}/${retries + 1}: TimeoutException - $e');
        if (attempt < retries) {
          await Future.delayed(Duration(seconds: 2 + attempt));
          continue;
        }
        return {'success': false, 'message': 'Connection timeout. Try again.'};
      }
      catch (e) { // noqa: broad-catch
        debugPrint('Upload error: $e');
        if (attempt < retries) {
          await Future.delayed(Duration(seconds: 2 + attempt));
          continue;
        }
        return {'success': false, 'message': 'Error: $e'};
      }
    }
    return {'success': false, 'message': 'Upload failed after retries'};
  }

  Future<bool> testConnection({int retries = 2, bool forceRefresh = false}) async {
    final device = _storage.getPairedDevice();
    if (device == null) return false;

    // Return cached result if fresh and not forced to refresh
    if (!forceRefresh && _lastConnectionCheck != null) {
      final age = DateTime.now().difference(_lastConnectionCheck!);
      if (age < CONNECTION_CACHE_TTL) {
        debugPrint('Using cached connection status: $_cachedConnectionStatus (age: ${age.inSeconds}s)');
        return _cachedConnectionStatus;
      }
    }

    for (int attempt = 0; attempt <= retries; attempt++) {
      try {
        final uri = Uri.parse('${device.serverUrl}/health');
        final response =
            await http.get(uri).timeout(const Duration(seconds: 3));
        if (response.statusCode == 200) {
          _cachedConnectionStatus = true;
          _lastConnectionCheck = DateTime.now();
          debugPrint('Connection test successful, cached for 30s');
          return true;
        }
      }
      on SocketException catch (e) {
        debugPrint('Connection test attempt ${attempt + 1}/${retries + 1}: SocketException - $e');
        if (attempt < retries) {
          await Future.delayed(Duration(seconds: 1 + attempt));
        }
      }
      on TimeoutException catch (e) {
        debugPrint('Connection test attempt ${attempt + 1}/${retries + 1}: TimeoutException - $e');
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
    debugPrint('Connection test failed, cached for 30s');
    return false;
  }

  Future<Map<String, dynamic>> checkSubmissionStatus(String submissionId) async {
    final device = _storage.getPairedDevice();
    if (device == null) {
      return {'success': false, 'message': 'Not paired'};
    }

    try {
      final uri = Uri.parse('${device.serverUrl}/api/mobile/inbox/$submissionId/status');
      final response = await http.get(
        uri,
        headers: {
          'Authorization': 'Bearer ${device.token}',
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return {
          'success': true,
          'status': data['status'],
          'processed_at': data['processed_at'],
        };
      }
      return {'success': false, 'message': 'Failed to get status'};
    } on TimeoutException {
      return {'success': false, 'message': 'Connection timeout'};
    }
    catch (e) { // noqa: broad-catch
      debugPrint('Check submission status error: $e');
      return {'success': false, 'message': 'Error: $e'};
    }
  }

  Future<Map<String, dynamic>> fetchCurrentTasks() async {
    final device = _storage.getPairedDevice();
    if (device == null) {
      return {'success': false, 'message': 'Not paired'};
    }

    try {
      final uri = Uri.parse('${device.serverUrl}/api/mobile/current-tasks');
      final response = await http.get(
        uri,
        headers: {
          'Authorization': 'Bearer ${device.token}',
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          // Cache tasks locally for offline viewing
          await _storage.cacheCurrentTasks(data['tasks'] ?? []);
          return {
            'success': true,
            'tasks': data['tasks'],
            'count': data['count'],
          };
        }
        return {'success': false, 'message': data['error'] ?? 'Failed to fetch'};
      } else if (response.statusCode == 401) {
        await _storage.clearPairing();
        return {'success': false, 'message': 'Session expired', 'unpaired': true};
      }
      return {'success': false, 'message': 'Server error: ${response.statusCode}'};
    } on SocketException {
      // Return cached tasks when offline
      final cached = await _storage.getCachedCurrentTasks();
      if (cached.isNotEmpty) {
        return {
          'success': true,
          'tasks': cached,
          'count': cached.length,
          'offline': true,
        };
      }
      return {'success': false, 'message': 'Cannot connect to PC'};
    } on TimeoutException {
      final cached = await _storage.getCachedCurrentTasks();
      if (cached.isNotEmpty) {
        return {
          'success': true,
          'tasks': cached,
          'count': cached.length,
          'offline': true,
        };
      }
      return {'success': false, 'message': 'Connection timeout'};
    }
    catch (e) { // noqa: broad-catch
      debugPrint('Fetch current tasks error: $e');
      return {'success': false, 'message': 'Error: $e'};
    }
  }

  Future<Map<String, dynamic>> fetchNotes() async {
    final device = _storage.getPairedDevice();
    if (device == null) {
      return {'success': false, 'message': 'Not paired'};
    }

    try {
      final uri = Uri.parse('${device.serverUrl}/api/mobile/notes');
      final response = await http.get(
        uri,
        headers: {
          'Authorization': 'Bearer ${device.token}',
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          await _storage.cacheNotes(data['notes'] ?? []);
          return {
            'success': true,
            'notes': data['notes'],
            'count': data['count'],
          };
        }
        return {'success': false, 'message': data['error'] ?? 'Failed to fetch'};
      } else if (response.statusCode == 401) {
        await _storage.clearPairing();
        return {'success': false, 'message': 'Session expired', 'unpaired': true};
      }
      return {'success': false, 'message': 'Server error: ${response.statusCode}'};
    } on SocketException {
      final cached = await _storage.getCachedNotes();
      if (cached.isNotEmpty) {
        return {
          'success': true,
          'notes': cached,
          'count': cached.length,
          'offline': true,
        };
      }
      return {'success': false, 'message': 'Cannot connect to PC'};
    } on TimeoutException {
      final cached = await _storage.getCachedNotes();
      if (cached.isNotEmpty) {
        return {
          'success': true,
          'notes': cached,
          'count': cached.length,
          'offline': true,
        };
      }
      return {'success': false, 'message': 'Connection timeout'};
    }
    catch (e) { // noqa: broad-catch
      debugPrint('Fetch notes error: $e');
      return {'success': false, 'message': 'Error: $e'};
    }
  }

  Future<Map<String, dynamic>> createNote(String title, String content) async {
    final device = _storage.getPairedDevice();
    if (device == null) {
      // Queue note for offline sync
      await _storage.queueOfflineNote(title, content);
      return {
        'success': true,
        'message': 'Note queued for sync when online',
        'offline': true,
      };
    }

    try {
      final uri = Uri.parse('${device.serverUrl}/api/mobile/notes');
      final response = await http
          .post(
            uri,
            headers: {
              'Content-Type': 'application/json',
              'Authorization': 'Bearer ${device.token}',
            },
            body: jsonEncode({
              'title': title,
              'content': content,
            }),
          )
          .timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          return {
            'success': true,
            'note': data['note'],
            'message': 'Note created successfully',
          };
        }
        return {'success': false, 'message': data['error'] ?? 'Failed to create note'};
      } else if (response.statusCode == 401) {
        await _storage.clearPairing();
        return {'success': false, 'message': 'Session expired', 'unpaired': true};
      }
      return {'success': false, 'message': 'Server error: ${response.statusCode}'};
    } on SocketException {
      await _storage.queueOfflineNote(title, content);
      return {
        'success': true,
        'message': 'Note queued for sync when online',
        'offline': true,
      };
    } on TimeoutException {
      await _storage.queueOfflineNote(title, content);
      return {
        'success': true,
        'message': 'Note queued for sync when online',
        'offline': true,
      };
    }
    catch (e) { // noqa: broad-catch
      debugPrint('Create note error: $e');
      return {'success': false, 'message': 'Error: $e'};
    }
  }

  Future<Map<String, dynamic>> checkSyncRequest() async {
    final device = _storage.getPairedDevice();
    if (device == null) {
      return {'success': false, 'sync_requested': false};
    }

    try {
      final uri = Uri.parse('${device.serverUrl}/api/mobile/sync-request');
      final response = await http.get(
        uri,
        headers: {
          'Authorization': 'Bearer ${device.token}',
        },
      ).timeout(const Duration(seconds: 10));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        return {
          'success': true,
          'sync_requested': data['sync_requested'] == true,
        };
      }
      return {'success': false, 'sync_requested': false};
    } on SocketException {
      return {'success': false, 'sync_requested': false};
    } on TimeoutException {
      return {'success': false, 'sync_requested': false};
    }
    catch (e) { // noqa: broad-catch
      debugPrint('Check sync request error: $e');
      return {'success': false, 'sync_requested': false};
    }
  }

  Future<void> syncOfflineNotes() async {
    final queue = await _storage.getOfflineNotesQueue();
    if (queue.isEmpty) return;

    debugPrint('Syncing ${queue.length} offline notes');
    final successful = <String>[];

    for (final note in queue) {
      final result = await createNote(
        note['title'] as String,
        note['content'] as String,
      );
      if (result['success'] == true && result['offline'] != true) {
        successful.add(note['id'] as String);
      }
    }

    if (successful.isNotEmpty) {
      await _storage.removeOfflineNotes(successful);
      debugPrint('Synced ${successful.length} offline notes');
    }
  }
}
