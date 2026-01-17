import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';

class DesktopTasksScreen extends StatefulWidget {
  const DesktopTasksScreen({super.key});

  @override
  State<DesktopTasksScreen> createState() => _DesktopTasksScreenState();
}

class _DesktopTasksScreenState extends State<DesktopTasksScreen> {
  final ApiService _api = ApiService();
  final StorageService _storage = StorageService();
  List<dynamic> _tasks = [];
  bool _isLoading = true;
  bool _isOffline = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadTasks();
  }

  Future<void> _loadTasks() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });

    if (!_storage.isPaired) {
      setState(() {
        _isLoading = false;
        _errorMessage = 'Not paired with PC. Please pair first.';
      });
      return;
    }

    final result = await _api.fetchCurrentTasks();

    if (mounted) {
      setState(() {
        _isLoading = false;
        if (result['success'] == true) {
          _tasks = List.from(result['tasks'] ?? []);
          _isOffline = result['offline'] == true;
          _errorMessage = null;
        } else {
          _errorMessage = result['message'] ?? 'Failed to load tasks';
          if (result['unpaired'] == true) {
            _errorMessage = 'Session expired. Please pair again.';
          }
        }
      });
    }
  }

  String _formatDueDate(String? dueDate) {
    if (dueDate == null || dueDate.isEmpty) return '';
    try {
      final date = DateTime.parse(dueDate);
      final now = DateTime.now();
      final today = DateTime(now.year, now.month, now.day);
      final taskDate = DateTime(date.year, date.month, date.day);
      
      if (taskDate == today) {
        return 'Today';
      } else if (taskDate == today.add(const Duration(days: 1))) {
        return 'Tomorrow';
      } else if (taskDate.isBefore(today)) {
        return 'Overdue';
      }
      return '${date.day}/${date.month}/${date.year}';
    }
    catch (e) {
      return dueDate;
    }
  }

  Color _getDueDateColor(String? dueDate) {
    if (dueDate == null || dueDate.isEmpty) return Colors.grey;
    try {
      final date = DateTime.parse(dueDate);
      final now = DateTime.now();
      final today = DateTime(now.year, now.month, now.day);
      final taskDate = DateTime(date.year, date.month, date.day);
      
      if (taskDate.isBefore(today)) {
        return Colors.red;
      } else if (taskDate == today) {
        return const Color(0xFFE85D04);
      } else if (taskDate == today.add(const Duration(days: 1))) {
        return Colors.orange;
      }
      return Colors.grey;
    }
    catch (e) {
      return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Desktop Tasks'),
        actions: [
          if (_isOffline)
            const Padding(
              padding: EdgeInsets.only(right: 8),
              child: Chip(
                label: Text('Offline', style: TextStyle(fontSize: 11)),
                backgroundColor: Colors.orange,
                padding: EdgeInsets.zero,
                visualDensity: VisualDensity.compact,
              ),
            ),
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadTasks,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: _buildBody(),
    );
  }

  Widget _buildBody() {
    if (_isLoading) {
      return const Center(
        child: CircularProgressIndicator(color: Color(0xFFE85D04)),
      );
    }

    if (_errorMessage != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                Icons.cloud_off,
                size: 64,
                color: Colors.grey[600],
              ),
              const SizedBox(height: 16),
              Text(
                _errorMessage!,
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 16,
                  color: Colors.grey[400],
                ),
              ),
              const SizedBox(height: 24),
              ElevatedButton.icon(
                onPressed: _loadTasks,
                icon: const Icon(Icons.refresh),
                label: const Text('Retry'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFFE85D04),
                ),
              ),
            ],
          ),
        ),
      );
    }

    if (_tasks.isEmpty) {
      return RefreshIndicator(
        onRefresh: _loadTasks,
        color: const Color(0xFFE85D04),
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            SizedBox(
              height: MediaQuery.of(context).size.height * 0.6,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(
                    Icons.check_circle_outline,
                    size: 64,
                    color: Colors.grey[600],
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'No active tasks',
                    style: TextStyle(
                      fontSize: 18,
                      color: Colors.grey[500],
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'All caught up! Pull to refresh.',
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.grey[600],
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: _loadTasks,
      color: const Color(0xFFE85D04),
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _tasks.length,
        itemBuilder: (context, index) {
          final task = _tasks[index];
          final title = task['title'] ?? 'Untitled';
          final description = task['description'] ?? '';
          final project = task['project'] ?? '';
          final dueDate = task['due_date']?.toString();
          final struckToday = task['struck_today'] == true;
          final completed = task['completed'] == true;
          final strikeCount = task['strike_count'] ?? 0;

          return Card(
            margin: const EdgeInsets.only(bottom: 12),
            color: struckToday || completed
                ? const Color(0xFF1A3A1A)
                : const Color(0xFF16213E),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Expanded(
                        child: Text(
                          title,
                          style: TextStyle(
                            fontSize: 16,
                            fontWeight: FontWeight.w600,
                            color: struckToday || completed
                                ? Colors.grey[400]
                                : Colors.white,
                            decoration: struckToday || completed
                                ? TextDecoration.lineThrough
                                : null,
                          ),
                        ),
                      ),
                      if (struckToday || completed)
                        const Icon(
                          Icons.check_circle,
                          color: Colors.green,
                          size: 20,
                        ),
                    ],
                  ),
                  if (description.isNotEmpty) ...[
                    const SizedBox(height: 8),
                    Text(
                      description,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: TextStyle(
                        fontSize: 14,
                        color: Colors.grey[400],
                      ),
                    ),
                  ],
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      if (project.isNotEmpty)
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: const Color(0xFFE85D04).withOpacity(0.2),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            project,
                            style: const TextStyle(
                              fontSize: 12,
                              color: Color(0xFFE85D04),
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                      if (dueDate != null && dueDate.isNotEmpty)
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: _getDueDateColor(dueDate).withOpacity(0.2),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Icon(
                                Icons.calendar_today,
                                size: 12,
                                color: _getDueDateColor(dueDate),
                              ),
                              const SizedBox(width: 4),
                              Text(
                                _formatDueDate(dueDate),
                                style: TextStyle(
                                  fontSize: 12,
                                  color: _getDueDateColor(dueDate),
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ],
                          ),
                        ),
                      if (strikeCount > 0)
                        Container(
                          padding: const EdgeInsets.symmetric(
                            horizontal: 10,
                            vertical: 4,
                          ),
                          decoration: BoxDecoration(
                            color: Colors.green.withOpacity(0.2),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Text(
                            '$strikeCount/${8} strikes',
                            style: const TextStyle(
                              fontSize: 12,
                              color: Colors.green,
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                    ],
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }
}
