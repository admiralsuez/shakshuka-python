import 'package:flutter/material.dart';
import 'package:flutter_slidable/flutter_slidable.dart';
import 'package:url_launcher/url_launcher.dart';
import '../models/task.dart';
import '../models/note.dart';
import '../services/storage_service.dart';
import '../services/api_service.dart';
import '../services/notification_service.dart';
import 'add_task_screen.dart';
import 'qr_scanner_screen.dart';
import 'desktop_tasks_screen.dart';
import 'notes_screen.dart';

class HomeScreen extends StatefulWidget {
  final void Function(String theme)? onThemeChanged;
  const HomeScreen({super.key, this.onThemeChanged});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final StorageService _storage = StorageService();
  final ApiService _api = ApiService();
  final NotificationService _notifications = NotificationService();
  final TextEditingController _quickAddController = TextEditingController();
  final FocusNode _quickAddFocus = FocusNode();
  bool _hasQuickDraft = false;
  List<LocalTask> _tasks = [];
  bool _isUploading = false;
  bool _isConnected = false;
  int _totalTasksSent = 0;
  bool _notPairedBarDismissed = false;
  String _appTheme = 'orange';

  @override
  void initState() {
    super.initState();
    _loadTasks();
    _checkConnection();
    _loadStats();
    _loadTheme();
    _quickAddController.addListener(_handleQuickAddChanged);
  }

  @override
  void dispose() {
    _quickAddController.removeListener(_handleQuickAddChanged);
    _quickAddController.dispose();
    _quickAddFocus.dispose();
    super.dispose();
  }

  void _handleQuickAddChanged() {
    final hasDraft = _quickAddController.text.trim().isNotEmpty;
    if (hasDraft != _hasQuickDraft) {
      setState(() {
        _hasQuickDraft = hasDraft;
      });
    }
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

  Future<void> _loadTheme() async {
    final theme = await _storage.getTheme();
    setState(() {
      _appTheme = theme;
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

  Future<void> _refreshData() async {
    await _checkConnection();
    _loadTasks();
    await _loadStats();
    await _notifications.checkTaskStatusUpdates();
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

  Future<void> _confirmDeleteTask(LocalTask task) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF16213E),
        title: const Text('Delete Task?'),
        content: Text('Are you sure you want to delete "${task.title}"?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Cancel'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            style: TextButton.styleFrom(foregroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    
    if (confirm == true) {
      await _deleteTask(task);
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
    final notes = _storage.getAllNotes();
    
    if (_tasks.isEmpty && notes.isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('No tasks or notes to upload')),
      );
      return;
    }

    if (!_storage.isPaired) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Please pair with your PC first')),
      );
      return;
    }

    // Show selection dialog
    final selection = await _showSendSelectionDialog(_tasks, notes);
    if (selection == null) {
      return;
    }

    final selectedTaskListDyn = (selection['tasks'] as List?) ?? const [];
    final selectedNoteListDyn = (selection['notes'] as List?) ?? const [];
    if (selectedTaskListDyn.isEmpty && selectedNoteListDyn.isEmpty) {
      return;
    }

    setState(() => _isUploading = true);

    final selectedTasks = List<LocalTask>.from(selectedTaskListDyn);
    final selectedNotes = List<LocalNote>.from(selectedNoteListDyn);
    final result = await _api.uploadTasksAndNotes(selectedTasks, selectedNotes);

    setState(() => _isUploading = false);

    if (result['success'] == true) {
      final tasksCount = result['tasks_count'] ?? selectedTasks.length;
      final notesCount = result['notes_count'] ?? selectedNotes.length;
      
      await _storage.incrementTasksSent(tasksCount);
      
      // Save history with submission_id for status tracking
      final taskData = selectedTasks.map((t) => {'title': t.title, 'duration': t.duration}).toList();
      final submissionId = result['submission_id'] as String?;
      await _storage.addSentTasksHistory(taskData, submissionId);
      
      // Remove sent items
      for (final task in selectedTasks) {
        await _storage.deleteTask(task.id);
      }
      for (final note in selectedNotes) {
        await _storage.deleteNote(note.id);
      }
      
      _loadTasks();
      _loadStats();
      
      // Show notification for successful upload
      String notifBody = '';
      if (tasksCount > 0 && notesCount > 0) {
        notifBody = '$tasksCount task(s) and $notesCount note(s) sent to PC inbox';
      } else if (tasksCount > 0) {
        notifBody = '$tasksCount task(s) sent to PC inbox';
      } else {
        notifBody = '$notesCount note(s) sent to PC inbox';
      }
      
      await _notifications.showTaskNotification(
        title: 'Upload Successful!',
        body: notifBody,
        submissionId: submissionId,
      );
      
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(result['message']),
            backgroundColor: Colors.green,
          ),
        );
      }
    } else {
      // Check if device was unpaired from desktop
      if (result['unpaired'] == true) {
        setState(() => _isConnected = false);
        if (mounted) {
          _showUnpairedDialog();
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
  }

  Future<Map<String, List>?> _showSendSelectionDialog(
    List<LocalTask> tasks,
    List<LocalNote> notes,
  ) async {
    final selectedTasks = List<LocalTask>.from(tasks);
    final selectedNotes = List<LocalNote>.from(notes);

    return showDialog<Map<String, List>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setState) => AlertDialog(
          backgroundColor: const Color(0xFF16213E),
          title: const Text('Send to PC'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (tasks.isNotEmpty) ...[
                  Row(
                    children: [
                      Checkbox(
                        value: selectedTasks.length == tasks.length,
                        tristate: selectedTasks.isNotEmpty && selectedTasks.length < tasks.length,
                        onChanged: (val) {
                          setState(() {
                            if (val == true) {
                              selectedTasks.clear();
                              selectedTasks.addAll(tasks);
                            } else {
                              selectedTasks.clear();
                            }
                          });
                        },
                      ),
                      Text(
                        'Tasks (${selectedTasks.length}/${tasks.length})',
                        style: const TextStyle(fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                  ...tasks.map((task) => CheckboxListTile(
                        dense: true,
                        title: Text(
                          task.title,
                          style: const TextStyle(fontSize: 14),
                        ),
                        value: selectedTasks.contains(task),
                        onChanged: (val) {
                          setState(() {
                            if (val == true) {
                              selectedTasks.add(task);
                            } else {
                              selectedTasks.remove(task);
                            }
                          });
                        },
                      )),
                  const SizedBox(height: 8),
                ],
                if (notes.isNotEmpty) ...[
                  Row(
                    children: [
                      Checkbox(
                        value: selectedNotes.length == notes.length,
                        tristate: selectedNotes.isNotEmpty && selectedNotes.length < notes.length,
                        onChanged: (val) {
                          setState(() {
                            if (val == true) {
                              selectedNotes.clear();
                              selectedNotes.addAll(notes);
                            } else {
                              selectedNotes.clear();
                            }
                          });
                        },
                      ),
                      Text(
                        'Notes (${selectedNotes.length}/${notes.length})',
                        style: const TextStyle(fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                  ...notes.map((note) => CheckboxListTile(
                        dense: true,
                        title: Text(
                          note.title,
                          style: const TextStyle(fontSize: 14),
                        ),
                        subtitle: Text(
                          note.content.length > 50
                              ? '${note.content.substring(0, 50)}...'
                              : note.content,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                        ),
                        value: selectedNotes.contains(note),
                        onChanged: (val) {
                          setState(() {
                            if (val == true) {
                              selectedNotes.add(note);
                            } else {
                              selectedNotes.remove(note);
                            }
                          });
                        },
                      )),
                ],
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Cancel'),
            ),
            ElevatedButton(
              onPressed: selectedTasks.isEmpty && selectedNotes.isEmpty
                  ? null
                  : () {
                      Navigator.pop(context, {
                        'tasks': selectedTasks,
                        'notes': selectedNotes,
                      });
                    },
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFE85D04),
              ),
              child: const Text('Send'),
            ),
          ],
        ),
      ),
    );
  }

  void _showUnpairedDialog() {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        backgroundColor: const Color(0xFF16213E),
        title: const Row(
          children: [
            Icon(Icons.link_off, color: Colors.orange),
            SizedBox(width: 12),
            Text('Device Unpaired'),
          ],
        ),
        content: const Text(
          'This device was unpaired from your PC. Your tasks are still saved locally.\n\nPlease pair again before sending tasks.',
          style: TextStyle(color: Colors.white70),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Later'),
          ),
          ElevatedButton.icon(
            onPressed: () {
              Navigator.pop(context);
              _openScanner();
            },
            icon: const Icon(Icons.qr_code_scanner),
            label: const Text('Pair Now'),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.orange,
            ),
          ),
        ],
      ),
    );
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
        contentPadding: const EdgeInsets.fromLTRB(24, 20, 24, 16),
        title: Row(
          children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(8),
              child: Image.asset(
                'assets/icon.png',
                width: 40,
                height: 40,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text(
                    'Shakshuka Companion',
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold),
                  ),
                  Text(
                    'v1.3 • $_totalTasksSent tasks sent',
                    style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                  ),
                ],
              ),
            ),
          ],
        ),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Add tasks on mobile, sync to PC via QR code pairing.',
              style: TextStyle(fontSize: 13, color: Colors.white70),
            ),
            const SizedBox(height: 16),
            // Links row
            Row(
              children: [
                Expanded(
                  child: InkWell(
                    onTap: () => _launchUrl('https://vibinandvanshika.in'),
                    borderRadius: BorderRadius.circular(8),
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      decoration: BoxDecoration(
                        border: Border.all(color: Colors.grey.shade700),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Column(
                        children: [
                          Icon(Icons.language, color: Color(0xFFE85D04), size: 20),
                          SizedBox(height: 4),
                          Text('Website', style: TextStyle(fontSize: 11, color: Colors.white70)),
                        ],
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: InkWell(
                    onTap: () => _launchUrl('https://github.com/admiralsuez/shakshuka-python'),
                    borderRadius: BorderRadius.circular(8),
                    child: Container(
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      decoration: BoxDecoration(
                        border: Border.all(color: Colors.grey.shade700),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: const Column(
                        children: [
                          Icon(Icons.code, color: Color(0xFFE85D04), size: 20),
                          SizedBox(height: 4),
                          Text('GitHub', style: TextStyle(fontSize: 11, color: Colors.white70)),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            Center(
              child: Text(
                'by vibinandvanshika',
                style: TextStyle(fontSize: 11, color: Colors.grey[600]),
              ),
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

  void _showChangelogPage() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => Scaffold(
          appBar: AppBar(
            title: const Text('Changelog'),
          ),
          body: ListView(
            padding: const EdgeInsets.all(16),
            children: const [
              _ChangelogEntry(
                version: '1.4.0',
                date: '2026-02-26',
                changes: [
                  'Added theme selector for the companion app (Orange, Dark/Blue, Self-Esteem/Mint, Anxiety/Sky, Yellow/Sunny) to mirror desktop appearance.',
                  'Theme preference is saved on device and applied across all screens, including quick-add, bottom Add bar, and Desktop Tasks view.',
                  'Notes screen now supports folders mirrored from desktop; the New Note dialog lets you pick an existing folder or type a new one, even when offline using cached folder names.',
                  'Stats page now refreshes pending submissions on open and lets you tap a sync entry to see the list of tasks that were sent.',
                ],
              ),
              _ChangelogEntry(
                version: '1.3.0',
                date: '2026-01-16',
                changes: [
                  'View desktop tasks from mobile',
                  'View and create notes synced with PC',
                  'Offline caching for tasks and notes',
                  'New drawer menu with Desktop Tasks and Notes',
                ],
              ),
              _ChangelogEntry(
                version: '1.2.0',
                date: '2025-12-28',
                changes: [
                  'Added local notifications for task uploads',
                  'Background polling for task approval/rejection status',
                  'Notification toggle in drawer menu',
                  'Delete confirmation dialog before removing tasks',
                  'Pull-to-refresh on task list',
                  'Changelog view in drawer menu',
                ],
              ),
              _ChangelogEntry(
                version: '1.1.0',
                date: '2025-12-27',
                changes: [
                  'Added project field to task form',
                  'Edit existing tasks before upload',
                  'Stats page with sync history',
                  'Task status tracking (pending/approved/rejected)',
                  'Improved About dialog with clickable links',
                ],
              ),
              _ChangelogEntry(
                version: '1.0.0',
                date: '2025-12-24',
                changes: [
                  'Initial release',
                  'QR code pairing with desktop app',
                  'Quick add tasks',
                  'Full task form with title, description, duration, due date',
                  'Offline task storage',
                  'Bulk task upload to PC inbox',
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _showStatsPage() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => _StatsPage(
          storage: _storage,
          notifications: _notifications,
          totalTasksSent: _totalTasksSent,
        ),
      ),
    );
  }

  Future<String?> _showThemeDialog() async {
    String current = _appTheme;
    return showDialog<String>(
      context: context,
      builder: (context) {
        return StatefulBuilder(
          builder: (context, setState) {
            return AlertDialog(
              backgroundColor: const Color(0xFF16213E),
              title: const Text('Choose Theme'),
              content: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  RadioListTile<String>(
                    value: 'orange',
                    groupValue: current,
                    title: const Text('Orange (Default)'),
                    onChanged: (v) => setState(() => current = v!),
                  ),
                  RadioListTile<String>(
                    value: 'dark',
                    groupValue: current,
                    title: const Text('Dark (Blue)'),
                    onChanged: (v) => setState(() => current = v!),
                  ),
                  RadioListTile<String>(
                    value: 'self-esteem',
                    groupValue: current,
                    title: const Text('Self-Esteem (Mint Green)'),
                    onChanged: (v) => setState(() => current = v!),
                  ),
                  RadioListTile<String>(
                    value: 'anxiety',
                    groupValue: current,
                    title: const Text('Anxiety (Sky Blue)'),
                    onChanged: (v) => setState(() => current = v!),
                  ),
                  RadioListTile<String>(
                    value: 'yellow',
                    groupValue: current,
                    title: const Text('Yellow (Sunny)'),
                    onChanged: (v) => setState(() => current = v!),
                  ),
                ],
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(context),
                  child: const Text('Cancel'),
                ),
                ElevatedButton(
                  onPressed: () => Navigator.pop(context, current),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFFE85D04),
                  ),
                  child: const Text('Apply'),
                ),
              ],
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final bool isPaired = _storage.isPaired;
    final bool needRepair = isPaired && !_isConnected;

    // Derive colors from active theme so quick-add and bottom bar react to
    // the selected desktop-mirrored palette (orange, dark/blue, mint, sky, yellow).
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final cardColor = theme.cardTheme.color ?? const Color(0xFF16213E);
    final surfaceVariant = theme.colorScheme.surfaceVariant;
    final primaryColor = colorScheme.primary;
    final onPrimary = colorScheme.onPrimary;
    final disabledColor = theme.disabledColor;

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
              isPaired
                  ? (needRepair ? Icons.link_off : Icons.link)
                  : Icons.link_off,
              size: 18,
              color: isPaired && _isConnected
                  ? Colors.green
                  : (needRepair ? Colors.orange : Colors.grey[400]),
            ),
            label: Text(
              isPaired
                  ? (needRepair ? 'NEED REPAIR' : 'PAIRED')
                  : 'PAIR',
              style: TextStyle(
                fontSize: 12,
                fontWeight: FontWeight.bold,
                color: isPaired && _isConnected
                    ? Colors.green
                    : (needRepair ? Colors.orange : Colors.grey[400]),
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
                  isPaired ? Icons.link : Icons.link_off,
                  color: isPaired
                      ? (needRepair ? Colors.orange : const Color(0xFFE85D04))
                      : Colors.grey[600],
                ),
                title: Text(isPaired ? 'Paired' : 'Pair with PC'),
                subtitle: isPaired
                    ? Text(
                        _isConnected
                            ? 'Connected'
                            : (needRepair ? 'Need repair' : 'Offline'),
                        style: TextStyle(
                          color: _isConnected ? const Color(0xFFE85D04) : Colors.orange,
                          fontSize: 12,
                        ),
                      )
                    : null,
                onTap: () {
                  Navigator.pop(context);
                  _openScanner();
                },
              ),
              const Divider(color: Colors.grey),
              ListTile(
                leading: Icon(
                  Icons.computer,
                  color: _storage.isPaired 
                      ? const Color(0xFFE85D04) 
                      : Colors.grey[600],
                ),
                title: const Text('Desktop Tasks'),
                subtitle: Text(
                  'View tasks from PC',
                  style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                ),
                onTap: () {
                  Navigator.pop(context);
                  Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const DesktopTasksScreen()),
                  );
                },
              ),
              ListTile(
                leading: Icon(
                  Icons.note,
                  color: _storage.isPaired 
                      ? const Color(0xFFE85D04) 
                      : Colors.grey[600],
                ),
                title: const Text('Notes'),
                subtitle: Text(
                  'View & create notes',
                  style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                ),
                onTap: () {
                  Navigator.pop(context);
                  Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => const NotesScreen()),
                  );
                },
              ),
              const Divider(color: Colors.grey),
              ListTile(
                leading: Icon(
                  Icons.color_lens,
                  color: Colors.grey[400],
                ),
                title: const Text('Theme'),
                subtitle: Text(
                  _appTheme == 'dark'
                      ? 'Dark (Blue)'
                      : _appTheme == 'self-esteem'
                          ? 'Self-Esteem (Mint Green)'
                          : _appTheme == 'anxiety'
                              ? 'Anxiety (Sky Blue)'
                              : _appTheme == 'yellow'
                                  ? 'Yellow (Sunny)'
                                  : 'Orange (Default)',
                  style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                ),
                onTap: () async {
                  Navigator.pop(context);
                  final newTheme = await _showThemeDialog();
                  if (newTheme != null && newTheme != _appTheme) {
                    await _storage.setTheme(newTheme);
                    setState(() {
                      _appTheme = newTheme;
                    });
                    if (widget.onThemeChanged != null) {
                      widget.onThemeChanged!(newTheme);
                    }
                  }
                },
              ),
              ListTile(
                leading: Icon(
                  Icons.bar_chart,
                  color: Colors.grey[400],
                ),
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
              ListTile(
                leading: Icon(
                  _notifications.notificationsEnabled 
                      ? Icons.notifications 
                      : Icons.notifications_off,
                  color: _notifications.notificationsEnabled 
                      ? const Color(0xFFE85D04) 
                      : Colors.grey[600],
                ),
                title: Text(
                  'Notifications',
                  style: TextStyle(
                    color: _notifications.notificationsEnabled 
                        ? Colors.white 
                        : Colors.grey[600],
                  ),
                ),
                subtitle: Text(
                  _notifications.notificationsEnabled 
                      ? 'Enabled' 
                      : 'Disabled',
                  style: TextStyle(
                    fontSize: 12,
                    color: Colors.grey[400],
                  ),
                ),
                onTap: () async {
                  final newValue = !_notifications.notificationsEnabled;
                  await _notifications.setNotificationsEnabled(newValue);
                  setState(() {}); // Rebuild to update icon
                  Navigator.pop(context);
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: Text(
                        newValue 
                            ? 'Notifications enabled' 
                            : 'Notifications disabled',
                      ),
                      duration: const Duration(seconds: 2),
                    ),
                  );
                },
              ),
              ListTile(
                leading: Icon(
                  Icons.history,
                  color: Colors.grey[400],
                ),
                title: const Text('Changelog'),
                subtitle: Text(
                  'v1.3.0',
                  style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                ),
                onTap: () {
                  Navigator.pop(context);
                  _showChangelogPage();
                },
              ),
              const Divider(color: Colors.grey),
              ListTile(
                leading: Icon(
                  Icons.info_outline,
                  color: Colors.grey[400],
                ),
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
                  'v1.3.0',
                  style: TextStyle(color: Colors.grey[600], fontSize: 12),
                ),
              ),
            ],
          ),
        ),
      ),
      body: Column(
        children: [
          // Offline indicator - not paired (clickable, dismissable)
          if (!isPaired && !_notPairedBarDismissed)
            GestureDetector(
              onTap: _openScanner,
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 16),
                decoration: BoxDecoration(
                  color: Colors.red.shade700,
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.3),
                      blurRadius: 4,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: const [
                          Icon(Icons.link_off, size: 18, color: Colors.white),
                          SizedBox(width: 8),
                          Text(
                            'Not paired - Tap to connect',
                            style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500),
                          ),
                        ],
                      ),
                    ),
                    GestureDetector(
                      onTap: () {
                        setState(() {
                          _notPairedBarDismissed = true;
                        });
                      },
                      child: const Padding(
                        padding: EdgeInsets.only(left: 8),
                        child: Icon(Icons.close, size: 18, color: Colors.white70),
                      ),
                    ),
                  ],
                ),
              ),
            )
          // Offline indicator - paired but disconnected (need repair)
          else if (needRepair)
            GestureDetector(
              onTap: _openScanner,
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 16),
                decoration: BoxDecoration(
                  color: Colors.orange.shade800,
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.3),
                      blurRadius: 4,
                      offset: const Offset(0, 2),
                    ),
                  ],
                ),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: const [
                    Icon(Icons.link_off, size: 18, color: Colors.white),
                    SizedBox(width: 8),
                    Text(
                      'Paired but offline - Tap to repair',
                      style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500),
                    ),
                  ],
                ),
              ),
            )
          // Offline indicator - generic offline (not paired banner already dismissed)
          else if (!_isConnected)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 16),
              decoration: BoxDecoration(
                color: Colors.orange.shade800,
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withOpacity(0.3),
                    blurRadius: 4,
                    offset: const Offset(0, 2),
                  ),
                ],
              ),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: const [
                  Icon(Icons.wifi_off, size: 18, color: Colors.white),
                  SizedBox(width: 8),
                  Text(
                    'Offline - Tasks saved locally',
                    style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500),
                  ),
                ],
              ),
            ),
          // Quick add input
          Container(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
            color: cardColor,
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
                      fillColor: surfaceVariant,
                      contentPadding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 12,
                      ),
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(10),
                        borderSide: BorderSide.none,
                      ),
                      suffixIcon: IconButton(
                        icon: Icon(Icons.add, color: primaryColor),
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

          // Task list with pull-to-refresh
          Expanded(
            child: RefreshIndicator(
              onRefresh: _refreshData,
              color: primaryColor,
              child: _tasks.isEmpty
                ? ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    children: [
                      SizedBox(
                        height: MediaQuery.of(context).size.height * 0.4,
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
                            const SizedBox(height: 16),
                            Text(
                              'Pull down to refresh',
                              style: TextStyle(
                                fontSize: 12,
                                color: Colors.grey[700],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
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
                                onPressed: (_) => _confirmDeleteTask(task),
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
          ),

          // Bottom bar with Send and Add buttons
          SafeArea(
            child: Container(
              padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
              decoration: BoxDecoration(
                color: cardColor,
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
                    child: FutureBuilder<int>(
                      future: Future.value(_storage.noteCount),
                      builder: (context, snapshot) {
                        final noteCount = snapshot.data ?? 0;
                        final totalCount = _tasks.length + noteCount;
                        final isEmpty = _tasks.isEmpty && noteCount == 0;
                        final composing = _hasQuickDraft;

                        String buttonText;
                        VoidCallback? onPressed;
                        Widget iconWidget;

                        if (_isUploading) {
                          buttonText = 'Sending...';
                          onPressed = null;
                          iconWidget = const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          );
                        } else if (composing) {
                          // While user is typing a quick-add task, repurpose the
                          // bottom button to save that task locally instead of
                          // sending items to the PC.
                          buttonText = 'Save task';
                          onPressed = () => _quickAddTask(_quickAddController.text);
                          iconWidget = const Icon(Icons.save, size: 20);
                        } else if (isEmpty) {
                          buttonText = 'No items';
                          onPressed = null;
                          iconWidget = const Icon(Icons.cloud_upload, size: 20);
                        } else if (_tasks.isEmpty) {
                          buttonText = 'Send $noteCount note${noteCount > 1 ? 's' : ''} to PC';
                          onPressed = _uploadTasks;
                          iconWidget = const Icon(Icons.cloud_upload, size: 20);
                        } else if (noteCount == 0) {
                          buttonText = 'Send ${_tasks.length} task${_tasks.length > 1 ? 's' : ''} to PC';
                          onPressed = _uploadTasks;
                          iconWidget = const Icon(Icons.cloud_upload, size: 20);
                        } else {
                          buttonText = 'Send $totalCount items to PC';
                          onPressed = _uploadTasks;
                          iconWidget = const Icon(Icons.cloud_upload, size: 20);
                        }
                        
                        return ElevatedButton.icon(
                          onPressed: onPressed,
                          icon: iconWidget,
                                  width: 18,
                                  height: 18,
                                  child:
                                      CircularProgressIndicator(strokeWidth: 2),
                                )
                              : const Icon(Icons.cloud_upload, size: 20),
                          label: Text(
                            buttonText,
                            style: const TextStyle(fontSize: 14),
                          ),
                          style: ElevatedButton.styleFrom(
                            backgroundColor: isEmpty
                                ? disabledColor
                                : primaryColor,
                            foregroundColor: onPrimary,
                            padding: const EdgeInsets.symmetric(vertical: 14),
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(10),
                            ),
                          ),
                        );
                      },
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
                        backgroundColor: primaryColor,
                        foregroundColor: onPrimary,
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

class _ChangelogEntry extends StatelessWidget {
  final String version;
  final String date;
  final List<String> changes;

  const _ChangelogEntry({
    required this.version,
    required this.date,
    required this.changes,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: const Color(0xFFE85D04),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Text(
                    'v$version',
                    style: const TextStyle(
                      color: Colors.white,
                      fontWeight: FontWeight.bold,
                      fontSize: 14,
                    ),
                  ),
                ),
                const SizedBox(width: 12),
                Text(
                  date,
                  style: TextStyle(
                    color: Colors.grey[500],
                    fontSize: 13,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            ...changes.map((change) => Padding(
              padding: const EdgeInsets.only(bottom: 6),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('• ', style: TextStyle(color: Color(0xFFE85D04))),
                  Expanded(
                    child: Text(
                      change,
                      style: TextStyle(
                        color: Colors.grey[300],
                        fontSize: 14,
                      ),
                    ),
                  ),
                ],
              ),
            )),
          ],
        ),
      ),
    );
  }
}

class _StatsPage extends StatefulWidget {
  final StorageService storage;
  final NotificationService notifications;
  final int totalTasksSent;

  const _StatsPage({
    required this.storage,
    required this.notifications,
    required this.totalTasksSent,
  });

  @override
  State<_StatsPage> createState() => _StatsPageState();
}

class _StatsPageState extends State<_StatsPage> {
  List<Map<String, dynamic>> _history = [];
  bool _isLoading = true;

  final ApiService _api = ApiService();

  @override
  void initState() {
    super.initState();
    _loadAndRefreshStatus();
  }

  Future<void> _loadAndRefreshStatus() async {
    setState(() => _isLoading = true);

    // First refresh status for any pending submissions directly from the
    // desktop API so the history view is always up to date even if background
    // notifications are disabled.
    final history = await widget.storage.getSentTasksHistory();
    for (final entry in history) {
      if (entry['status'] != 'pending') {
        continue;
      }
      final submissionId = entry['submission_id'] as String?;
      if (submissionId == null || submissionId.isEmpty) {
        continue;
      }
      final statusResult = await _api.checkSubmissionStatus(submissionId);
      if (statusResult['success'] == true &&
          statusResult['status'] is String &&
          statusResult['status'] != 'pending') {
        await widget.storage.updateHistoryStatus(
          submissionId,
          statusResult['status'] as String,
        );
      }
    }

    // Then load the (possibly updated) history
    final refreshed = await widget.storage.getSentTasksHistory();

    if (mounted) {
      setState(() {
        _history = refreshed;
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Stats & History'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: _loadAndRefreshStatus,
            tooltip: 'Refresh status',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator())
          : RefreshIndicator(
              onRefresh: _loadAndRefreshStatus,
              child: Column(
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
                              '${widget.totalTasksSent}',
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
                              '${_history.length}',
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
                    child: _history.isEmpty
                        ? ListView(
                            children: [
                              SizedBox(
                                height: MediaQuery.of(context).size.height * 0.4,
                                child: Center(
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
                                ),
                              ),
                            ],
                          )
                        : ListView.builder(
                            padding: const EdgeInsets.symmetric(horizontal: 16),
                            itemCount: _history.length,
                            itemBuilder: (context, index) {
                              final entry = _history[index];
                              final timestamp = DateTime.tryParse(
                                entry['timestamp'] ?? '',
                              );
                              final status = entry['status'] ?? (entry['accepted'] == true ? 'approved' : 'pending');
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
                                  onTap: () {
                                    showDialog(
                                      context: context,
                                      builder: (context) {
                                        return AlertDialog(
                                          backgroundColor: const Color(0xFF16213E),
                                          title: Text(
                                            'Sync details (${statusText.toLowerCase()})',
                                            style: const TextStyle(fontSize: 16),
                                          ),
                                          content: SizedBox(
                                            width: double.maxFinite,
                                            child: Column(
                                              mainAxisSize: MainAxisSize.min,
                                              crossAxisAlignment: CrossAxisAlignment.start,
                                              children: [
                                                if (timestamp != null)
                                                  Padding(
                                                    padding: const EdgeInsets.only(bottom: 8),
                                                    child: Text(
                                                      'Time: ${timestamp.day}/${timestamp.month}/${timestamp.year} ${timestamp.hour}:${timestamp.minute.toString().padLeft(2, '0')}',
                                                      style: TextStyle(
                                                        fontSize: 12,
                                                        color: Colors.grey[400],
                                                      ),
                                                    ),
                                                  ),
                                                Text(
                                                  'Tasks:',
                                                  style: TextStyle(
                                                    fontSize: 13,
                                                    fontWeight: FontWeight.bold,
                                                    color: Colors.grey[200],
                                                  ),
                                                ),
                                                const SizedBox(height: 4),
                                                ...tasks.map((t) => Padding(
                                                      padding: const EdgeInsets.only(bottom: 4),
                                                      child: Text(
                                                        '- ${t['title'] ?? 'Untitled'}',
                                                        style: TextStyle(
                                                          fontSize: 13,
                                                          color: Colors.grey[300],
                                                        ),
                                                      ),
                                                    )),
                                              ],
                                            ),
                                          ),
                                          actions: [
                                            TextButton(
                                              onPressed: () => Navigator.pop(context),
                                              child: const Text('Close'),
                                            ),
                                          ],
                                        );
                                      },
                                    );
                                  },
                                ),
                              );
                            },
                          ),
                  ),
                ],
              ),
            ),
    );
  }
}
