import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:http/http.dart' as http;
import 'storage_service.dart';

class NotificationService {
  static final NotificationService _instance = NotificationService._internal();
  factory NotificationService() => _instance;
  NotificationService._internal();

  final FlutterLocalNotificationsPlugin _notifications =
      FlutterLocalNotificationsPlugin();

  bool _isInitialized = false;
  bool _notificationsEnabled = true;

  Future<void> initialize() async {
    if (_isInitialized) return;

    const AndroidInitializationSettings androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');

    const DarwinInitializationSettings iosSettings =
        DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );

    const InitializationSettings settings =
        InitializationSettings(android: androidSettings, iOS: iosSettings);

    await _notifications.initialize(
      settings,
      onDidReceiveNotificationResponse: _onNotificationTapped,
    );

    final prefs = await SharedPreferences.getInstance();
    _notificationsEnabled = prefs.getBool('notifications_enabled') ?? true;

    _isInitialized = true;
  }

  void _onNotificationTapped(NotificationResponse response) {
    if (kDebugMode) {
      print('Notification tapped: ${response.payload}');
    }
  }

  Future<void> _showNotification({
    required String title,
    required String body,
    String? payload,
    int id = 0,
  }) async {
    const AndroidNotificationDetails androidDetails =
        AndroidNotificationDetails(
      'shakshuka_channel',
      'Shakshuka Notifications',
      channelDescription: 'Notifications for task updates',
      importance: Importance.high,
      priority: Priority.high,
      showWhen: true,
    );

    const DarwinNotificationDetails iosDetails = DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: true,
      presentSound: true,
    );

    const NotificationDetails notificationDetails = NotificationDetails(
      android: androidDetails,
      iOS: iosDetails,
    );

    await _notifications.show(id, title, body, notificationDetails,
        payload: payload);
  }

  Future<void> setNotificationsEnabled(bool enabled) async {
    _notificationsEnabled = enabled;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setBool('notifications_enabled', enabled);

    if (!enabled) {
      await _notifications.cancelAll();
    }
  }

  bool get notificationsEnabled => _notificationsEnabled;

  Future<void> showTaskNotification({
    required String title,
    required String body,
    String? submissionId,
  }) async {
    if (!_notificationsEnabled) return;
    await _showNotification(title: title, body: body, payload: submissionId);
  }

  Future<void> checkTaskStatusUpdates() async {
    if (!_notificationsEnabled) return;

    final storage = StorageService();
    final device = storage.getPairedDevice();
    if (device == null) return;

    final history = await storage.getSentTasksHistory();
    final pendingSubmissions =
        history.where((e) => e['status'] == 'pending').toList();

    for (final entry in pendingSubmissions) {
      final submissionId = entry['submission_id'] as String?;
      if (submissionId == null) continue;

      try {
        final uri = Uri.parse(
            '${device.serverUrl}/api/mobile/inbox/$submissionId/status');
        final response = await http.get(
          uri,
          headers: {'Authorization': 'Bearer ${device.token}'},
        ).timeout(const Duration(seconds: 10));

        if (response.statusCode == 200) {
          final data = jsonDecode(response.body);
          final status = data['status'] as String?;

          if (status != null && status != 'pending') {
            await storage.updateHistoryStatus(submissionId, status);

            final tasks = List.from(entry['tasks'] ?? []);
            final taskCount = tasks.length;
            final firstTask =
                tasks.isNotEmpty ? tasks.first['title'] ?? 'Task' : 'Task';

            if (status == 'approved') {
              await _showNotification(
                title: 'Tasks Approved!',
                body: taskCount > 1
                    ? '$taskCount tasks including "$firstTask" were approved'
                    : '"$firstTask" was approved',
                payload: submissionId,
                id: submissionId.hashCode,
              );
            } else if (status == 'rejected') {
              await _showNotification(
                title: 'Tasks Rejected',
                body: taskCount > 1
                    ? '$taskCount tasks including "$firstTask" were rejected'
                    : '"$firstTask" was rejected',
                payload: submissionId,
                id: submissionId.hashCode,
              );
            }
          }
        }
      } on TimeoutException {
        if (kDebugMode) {
          print('Timeout checking status for $submissionId');
        }
      }
      catch (e) { // noqa: broad-catch
        if (kDebugMode) {
          print('Error checking status for $submissionId: $e');
        }
      }
    }
  }
}
