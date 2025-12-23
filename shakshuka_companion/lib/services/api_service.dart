import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import '../models/task.dart';
import '../models/paired_device.dart';
import 'storage_service.dart';

class ApiService {
  static final ApiService _instance = ApiService._internal();
  factory ApiService() => _instance;
  ApiService._internal();

  final StorageService _storage = StorageService();

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
          return {'success': true, 'message': 'Paired successfully!'};
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
    } catch (e) {
      return {'success': false, 'message': 'Error: $e'};
    }
  }

  Future<Map<String, dynamic>> uploadTasks(List<LocalTask> tasks) async {
    final device = _storage.getPairedDevice();
    if (device == null) {
      return {'success': false, 'message': 'Not paired with any PC'};
    }

    if (tasks.isEmpty) {
      return {'success': false, 'message': 'No tasks to upload'};
    }

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
            }),
          )
          .timeout(const Duration(seconds: 15));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        if (data['success'] == true) {
          return {
            'success': true,
            'message': 'Uploaded ${tasks.length} task(s) to PC inbox!',
            'submission_id': data['submission_id'],
          };
        }
        return {
          'success': false,
          'message': data['error'] ?? 'Upload failed'
        };
      } else if (response.statusCode == 401) {
        return {
          'success': false,
          'message': 'Authentication failed. Please re-pair with your PC.'
        };
      } else {
        return {
          'success': false,
          'message': 'Server error: ${response.statusCode}'
        };
      }
    } on SocketException {
      return {'success': false, 'message': 'Cannot connect to PC'};
    } on http.ClientException {
      return {'success': false, 'message': 'Connection failed'};
    } catch (e) {
      return {'success': false, 'message': 'Error: $e'};
    }
  }

  Future<bool> testConnection() async {
    final device = _storage.getPairedDevice();
    if (device == null) return false;

    try {
      final uri = Uri.parse('${device.serverUrl}/health');
      final response =
          await http.get(uri).timeout(const Duration(seconds: 5));
      return response.statusCode == 200;
    } catch (_) {
      return false;
    }
  }
}
