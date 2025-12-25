import 'package:flutter/material.dart';
import 'package:flutter_slidable/flutter_slidable.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/task.dart';
import '../services/storage_service.dart';
import '../services/api_service.dart';
import 'add_task_screen.dart';
import 'qr_scanner_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final StorageService _storage = StorageService();
  final ApiService _api = ApiService();
  final TextEditingController _quickAddController = TextEditingController();
  final FocusNode _quickAddFocus = FocusNode();
  List<LocalTask> _tasks = [];
  bool _isUploading = false;
  bool _isConnected = false;
  int _totalTasksSent = 0;

  @override
  void initState() {
    super.initState();
    _loadTasks();
    _checkConnection();
    _loadStats();
  }

  @override
  void dispose() {
    _quickAddController.dispose();
    _quickAddFocus.dispose();
    super.dispose();
  }

  void _loadTasks() {
    setState(() {
      _tasks = _storage.getAllTasks();
    });
  }

  Future<void> _loadStats() async {
    final stats = await _storage.getStats();
    setState(() {
      _totalTasksSent = stats['totalSent'] ?? 0;
    });
  }

  Future<void> _checkConnection() async {
    if (_storage.isPaired) {
      final connected = await _api.testConnection();
      setState(() => _isConnected = connected);
    } else {
      setState(() => _isConnected = false);
    }
  }

  Future<void> _quickAddTask(String title) async {
    final trimmed = title.trim();
    if (trimmed.isEmpty) return;

    final task = LocalTask(title: trimmed, duration: 30);
    await _storage.addTask(task);
    _quickAddController.clear();
    _loadTasks();
  }

  Future<void> _addTask() async {
    final result = await Navigator.push<LocalTask>(
      context,
      MaterialPageRoute(builder: (_) => const AddTaskScreen()),
    );
    if (result != null) {
      await _storage.addTask(result);
      _loadTasks();
    }
  }

  Future<void> _deleteTask(LocalTask task) async {
    await _storage.deleteTask(task.id);
    _loadTasks();
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text('Deleted "${task.title}"'),
          action: SnackBarAction(
            label: 'Undo',
            onPressed: () async {
              await _storage.addTask(task);
              _loadTasks();
            },
          ),
        ),
      );
    }
  }

  Future<void> _editTask(LocalTask task) async {
    final result = await Navigator.push<LocalTask>(
      context,
      MaterialPageRoute(builder: (_) => AddTaskScreen(taskToEdit: task)),
    );
    if (result != null) {
      await _storage.updateTask(result);
      _loadTasks();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Task updated'),
            backgroundColor: Colors.green,
          ),
        );
      }
    }
  }

  Future<void> _uploadTasks() async {
    if (_tasks.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No tasks to upload')),
      );
      return;
    }

    if (!_storage.isPaired) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please pair with your PC first')),
      );
      return;
    }

    setState(() => _isUploading = true);

    final taskCount = _tasks.length;
    final result = await _api.uploadTasks(_tasks);

    setState(() => _isUploading = false);

    if (result['success'] == true) {
      await _storage.incrementTasksSent(taskCount);
      // Save history with submission_id for status tracking
      final taskData = _tasks.map((t) => {'title': t.title, 'duration': t.duration}).toList();
      final submissionId = result['submission_id'] as String?;
      await _storage.addSentTasksHistory(taskData, submissionId);
      await _storage.clearAllTasks();
      _loadTasks();
      _loadStats();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(result['message']),
            backgroundColor: Colors.green,
          ),
        );
      }
    } else {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(result['message']),
            backgroundColor: Colors.red,
          ),
        );
      }
    }
  }

  Future<void> _openScanner() async {
    final result = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => const QRScannerScreen()),
    );
    if (result == true) {
      _checkConnection();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Successfully paired with PC!'),
            backgroundColor: Colors.green,
          ),
        );
      }
    }
  }

  Future<void> _launchUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  void _showAboutDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF16213E),
        title: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: Image.asset(
                'assets/icon.png',
                width: 32,
                height: 32,
              ),
            ),
            const SizedBox(width: 8),
            const Expanded(
              child: Text(
                'Shakshuka Companion',
                style: TextStyle(fontSize: 18),
                overflow: TextOverflow.ellipsis,
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'A companion app for Shakshuka Task Manager.',
              style: TextStyle(fontSize: 14),
            ),
            const SizedBox(height: 16),
            Text(
              'Tasks sent to PC: $_totalTasksSent',
              style: TextStyle(fontSize: 13, color: Colors.grey[400]),
            ),
            const SizedBox(height: 8),
            const Text(
              'Version 1.0',
              style: TextStyle(fontSize: 13, color: Colors.grey),
            ),
            const SizedBox(height: 16),
            const Text(
              'Add tasks on your phone, sync them to your PC with one tap.',
              style: TextStyle(fontSize: 13),
            ),
            const SizedBox(height: 16),
            const Divider(color: Colors.grey),
            const SizedBox(height: 8),
            const Text(
              'By vibinandvanshika',
              style: TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
            ),
            const SizedBox(height: 8),
            GestureDetector(
              onTap: () => _launchUrl('https://vibinandvanshika.in'),
              child: const Text(
                '🌐 vibinandvanshika.in',
                style: TextStyle(
                  fontSize: 13,
                  color: Color(0xFFE85D04),
                  decoration: TextDecoration.underline,
                ),
              ),
            ),
            const SizedBox(height: 4),
            GestureDetector(
              onTap: () => _launchUrl('https://github.com/admiralsuez/shakshuka-python'),
              child: const Text(
                '📦 github.com/admiralsuez/shakshuka-python',
                style: TextStyle(
                  fontSize: 12,
                  color: Color(0xFFE85D04),
                  decoration: TextDecoration.underline,
                ),
              ),
            ),
            const SizedBox(height: 16),
            const Divider(color: Colors.grey),
            const SizedBox(height: 8),
            const Text(
              'Get the app:',
              style: TextStyle(fontSize: 12, color: Colors.grey),
            ),
            const SizedBox(height: 8),
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                GestureDetector(
                  onTap: () => _launchUrl('https://play.google.com/store/apps/details?id=com.shakshuka.companion'),
                  child: Image.asset(
                    'assets/google-play-badge.png',
                    height: 40,
                  ),
                ),
                const SizedBox(width: 8),
                GestureDetector(
                  onTap: () => _launchUrl('https://f-droid.org/packages/com.shakshuka.companion'),
                  child: Image.asset(
                    'assets/fdroid-badge.png',
                    height: 40,
                  ),
                ),
              ],
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Close'),
          ),
        ],
      ),
    );
  }

  void _showStatsPage() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => Scaffold(
          appBar: AppBar(
            title: const Text('Stats & History'),
          ),
          body: FutureBuilder<List<Map<String, dynamic>>>(
            future: _storage.getSentTasksHistory(),
            builder: (context, snapshot) {
              final history = snapshot.data ?? [];
              
              return Column(
                children: [
                  // Stats summary
                  Container(
                    padding: const EdgeInsets.all(20),
                    margin: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: const Color(0xFF16213E),
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceAround,
                      children: [
                        Column(
                          children: [
                            Text(
                              '$_totalTasksSent',
                              style: const TextStyle(
                                fontSize: 32,
                                fontWeight: FontWeight.bold,
                                color: Color(0xFFE85D04),
                              ),
                            ),
                            Text(
                              'Tasks Sent',
                              style: TextStyle(
                                fontSize: 14,
                                color: Colors.grey[400],
                              ),
                            ),
                          ],
                        ),
                        Column(
                          children: [
                            Text(
                              '${history.length}',
                              style: const TextStyle(
                                fontSize: 32,
                                fontWeight: FontWeight.bold,
                                color: Colors.blue,
                              ),
                            ),
                            Text(
                              'Syncs',
                              style: TextStyle(
                                fontSize: 14,
                                color: Colors.grey[400],
                              ),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                  
                  // History list
                  Expanded(
                    child: history.isEmpty
                        ? Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(
                                  Icons.history,
                                  size: 64,
                                  color: Colors.grey[600],
                                ),
                                const SizedBox(height: 16),
                                Text(
                                  'No sync history yet',
                                  style: TextStyle(
                                    fontSize: 16,
                                    color: Colors.grey[500],
                                  ),
                                ),
                              ],
                            ),
                          )
                        : ListView.builder(
                            padding: const EdgeInsets.symmetric(horizontal: 16),
                            itemCount: history.length,
                            itemBuilder: (context, index) {
                              final entry = history[index];
                              final timestamp = DateTime.tryParse(
                                entry['timestamp'] ?? '',
                              );
                              final status = entry['status'] ?? (entry['accepted'] == true ? 'approved' : 'rejected');
                              final tasks = List.from(entry['tasks'] ?? []);
                              
                              IconData statusIcon;
                              Color statusColor;
                              String statusText;
                              
                              switch (status) {
                                case 'approved':
                                  statusIcon = Icons.check_circle;
                                  statusColor = Colors.green;
                                  statusText = 'Accepted';
                                  break;
                                case 'rejected':
                                  statusIcon = Icons.cancel;
                                  statusColor = Colors.red;
                                  statusText = 'Rejected';
                                  break;
                                default:
                                  statusIcon = Icons.hourglass_empty;
                                  statusColor = Colors.orange;
                                  statusText = 'Pending';
                              }
                              
                              return Card(
                                margin: const EdgeInsets.only(bottom: 8),
                                child: ListTile(
                                  leading: Icon(
                                    statusIcon,
                                    color: statusColor,
                                    size: 28,
                                  ),
                                  title: Text(
                                    '${tasks.length} task(s)',
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                  subtitle: Column(
                                    crossAxisAlignment: CrossAxisAlignment.start,
                                    children: [
                                      if (timestamp != null)
                                        Text(
                                          '${timestamp.day}/${timestamp.month}/${timestamp.year} ${timestamp.hour}:${timestamp.minute.toString().padLeft(2, '0')}',
                                          style: TextStyle(
                                            fontSize: 12,
                                            color: Colors.grey[500],
                                          ),
                                        ),
                                      const SizedBox(height: 4),
                                      Text(
                                        tasks.map((t) => t['title'] ?? '').join(', '),
                                        maxLines: 1,
                                        overflow: TextOverflow.ellipsis,
                                        style: TextStyle(
                                          fontSize: 12,
                                          color: Colors.grey[400],
                                        ),
                                      ),
                                    ],
                                  ),
                                  trailing: Text(
                                    statusText,
                                    style: TextStyle(
                                      fontSize: 12,
                                      color: statusColor,
                                    ),
                                  ),
                                ),
                              );
                            },
                          ),
                  ),
                ],
              );
            },
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        leading: Builder(
          builder: (context) => IconButton(
            icon: const Icon(Icons.menu),
            onPressed: () => Scaffold.of(context).openDrawer(),
          ),
        ),
        title: const Text('Shakshuka Companion'),
        actions: [
          TextButton.icon(
            onPressed: _openScanner,
            icon: Icon(
              _storage.isPaired ? Icons.link : Icons.link_off,
              size: 18,
              color: _storage.isPaired && _isConnected
                  ? Colors.green
                  : Colors.grey[400],
            ),
            label: Text(
              _storage.isPaired ? 'PAIRED' : 'PAIR',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.bold,
                color: _storage.isPaired && _isConnected
                    ? Colors.green
                    : Colors.grey[400],
              ),
            ),
          ),
        ],
      ),
      drawer: Drawer(
        backgroundColor: const Color(0xFF16213E),
        child: SafeArea(
          child: Column(
            children: [
              Container(
                padding: const EdgeInsets.all(20),
                child: Row(
                  children: [
                    Container(
                      width: 48,
                      height: 48,
                      decoration: BoxDecoration(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Image.asset(
                        'assets/icon.png',
                        errorBuilder: (context, error, stackTrace) => const Text('🍳', style: TextStyle(fontSize: 32)),
                      ),
                    ),
                    const SizedBox(width: 12),
                    const Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Shakshuka',
                          style: TextStyle(
                            fontSize: 20,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        Text(
                          'Companion',
                          style: TextStyle(
                            fontSize: 14,
                            color: Colors.grey,
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const Divider(color: Colors.grey),
              ListTile(
                leading: Icon(
                  _storage.isPaired ? Icons.link : Icons.link_off,
                  color: _storage.isPaired ? Colors.green : Colors.grey,
                ),
                title: Text(_storage.isPaired ? 'Paired' : 'Pair with PC'),
                subtitle: _storage.isPaired
                    ? Text(
                        _isConnected ? 'Connected' : 'Offline',
                        style: TextStyle(
                          color: _isConnected ? Colors.green : Colors.orange,
                          fontSize: 12,
                        ),
                      )
                    : null,
                onTap: () {
                  Navigator.pop(context);
                  _openScanner();
                },
              ),
              ListTile(
                leading: const Icon(Icons.bar_chart, color: Colors.blue),
                title: const Text('Stats'),
                subtitle: Text(
                  '$_totalTasksSent tasks sent',
                  style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                ),
                onTap: () {
                  Navigator.pop(context);
                  _showStatsPage();
                },
              ),
              const Divider(color: Colors.grey),
              ListTile(
                leading: const Icon(Icons.info_outline, color: Colors.grey),
                title: const Text('About'),
                onTap: () {
                  Navigator.pop(context);
                  _showAboutDialog();
                },
              ),
              const Spacer(),
              Padding(
                padding: const EdgeInsets.all(16),
                child: Text(
                  'v1.0',
                  style: TextStyle(color: Colors.grey[600], fontSize: 12),
                ),
              ),
            ],
          ),
        ),
      ),
      body: Column(
        children: [
          // Offline indicator
          if (!_isConnected && _storage.isPaired)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
              color: Colors.orange.shade800,
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  const Icon(Icons.wifi_off, size: 16, color: Colors.white),
                  const SizedBox(width: 8),
                  const Text(
                    'Offline - Tasks will sync when connected',
                    style: TextStyle(color: Colors.white, fontSize: 12),
                  ),
                ],
              ),
            ),
          // Quick add input
          Container(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
            color: const Color(0xFF16213E),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _quickAddController,
                    focusNode: _quickAddFocus,
                    style: const TextStyle(color: Colors.white),
                    decoration: InputDecoration(
                      hintText: 'Quick add task...',
                      hintStyle: TextStyle(color: Colors.grey[500]),
                      filled: true,
                      fillColor: const Color(0xFF1A1A2E),
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 12,
                      ),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: BorderSide.none,
                      ),
                      suffixIcon: IconButton(
                        icon: const Icon(Icons.add, color: Color(0xFFE85D04)),
                        onPressed: () =>
                            _quickAddTask(_quickAddController.text),
                      ),
                    ),
                    onSubmitted: _quickAddTask,
                  ),
                ),
              ],
            ),
          ),

          // Task list
          Expanded(
            child: _tasks.isEmpty
                ? Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          Icons.task_alt,
                          size: 64,
                          color: Colors.grey[600],
                        ),
                        const SizedBox(height: 16),
                        Text(
                          'No tasks yet',
                          style: TextStyle(
                            fontSize: 18,
                            color: Colors.grey[500],
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text(
                          'Use quick add above or tap +',
                          style: TextStyle(
                            fontSize: 14,
                            color: Colors.grey[600],
                          ),
                        ),
                      ],
                    ),
                  )
                : ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _tasks.length,
                    itemBuilder: (context, index) {
                      final task = _tasks[index];
                      return Padding(
                        padding: const EdgeInsets.only(bottom: 8),
                        child: Slidable(
                          startActionPane: ActionPane(
                            motion: const ScrollMotion(),
                            children: [
                              SlidableAction(
                                onPressed: (_) => _editTask(task),
                                backgroundColor: const Color(0xFFE85D04),
                                foregroundColor: Colors.white,
                                icon: Icons.edit,
                                label: 'Edit',
                                borderRadius: BorderRadius.circular(12),
                              ),
                            ],
                          ),
                          endActionPane: ActionPane(
                            motion: const ScrollMotion(),
                            children: [
                              SlidableAction(
                                onPressed: (_) => _deleteTask(task),
                                backgroundColor: Colors.red,
                                foregroundColor: Colors.white,
                                icon: Icons.delete,
                                label: 'Delete',
                                borderRadius: BorderRadius.circular(12),
                              ),
                            ],
                          ),
                          child: Card(
                            child: ListTile(
                              title: Text(
                                task.title,
                                style: const TextStyle(
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                              subtitle: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  if (task.description?.isNotEmpty == true)
                                    Padding(
                                      padding: const EdgeInsets.only(top: 4),
                                      child: Text(
                                        task.description!,
                                        maxLines: 2,
                                        overflow: TextOverflow.ellipsis,
                                        style: TextStyle(
                                          color: Colors.grey[400],
                                        ),
                                      ),
                                    ),
                                  const SizedBox(height: 4),
                                  Row(
                                    children: [
                                      if (task.duration != null) ...[
                                        Icon(
                                          Icons.timer_outlined,
                                          size: 14,
                                          color: Colors.grey[500],
                                        ),
                                        const SizedBox(width: 4),
                                        Text(
                                          '${task.duration} min',
                                          style: TextStyle(
                                            fontSize: 12,
                                            color: Colors.grey[500],
                                          ),
                                        ),
                                        const SizedBox(width: 12),
                                      ],
                                      if (task.dueDate != null) ...[
                                        Icon(
                                          Icons.calendar_today,
                                          size: 14,
                                          color: Colors.grey[500],
                                        ),
                                        const SizedBox(width: 4),
                                        Text(
                                          task.dueDate!,
                                          style: TextStyle(
                                            fontSize: 12,
                                            color: Colors.grey[500],
                                          ),
                                        ),
                                      ],
                                    ],
                                  ),
                                ],
                              ),
                              trailing: const Icon(
                                Icons.chevron_left,
                                color: Colors.grey,
                              ),
                            ),
                          ),
                        ),
                      );
                    },
                  ),
          ),

          // Bottom bar with Send and Add buttons
          SafeArea(
            child: Container(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
              decoration: BoxDecoration(
                color: const Color(0xFF16213E),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.3),
                    blurRadius: 8,
                    offset: const Offset(0, -2),
                  ),
                ],
              ),
              child: Row(
                children: [
                  // Send button
                  Expanded(
                    child: ElevatedButton.icon(
                      onPressed: _tasks.isEmpty || _isUploading
                          ? null
                          : _uploadTasks,
                      icon: _isUploading
                          ? const SizedBox(
                              width: 18,
                              height: 18,
                              child:
                                  CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.cloud_upload, size: 20),
                      label: Text(
                        _isUploading
                            ? 'Sending...'
                            : _tasks.isEmpty
                                ? 'No tasks'
                                : 'Send ${_tasks.length}',
                        style: const TextStyle(fontSize: 14),
                      ),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _tasks.isEmpty
                            ? Colors.grey[700]
                            : const Color(0xFFE85D04),
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  // Add button
                  SizedBox(
                    width: 56,
                    height: 48,
                    child: ElevatedButton(
                      onPressed: _addTask,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFFE85D04),
                        foregroundColor: Colors.white,
                        padding: EdgeInsets.zero,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(10),
                        ),
                      ),
                      child: const Icon(Icons.add, size: 28),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
