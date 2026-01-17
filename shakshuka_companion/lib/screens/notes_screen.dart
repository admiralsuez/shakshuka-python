import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';

class NotesScreen extends StatefulWidget {
  const NotesScreen({super.key});

  @override
  State<NotesScreen> createState() => _NotesScreenState();
}

class _NotesScreenState extends State<NotesScreen> {
  final ApiService _api = ApiService();
  final StorageService _storage = StorageService();
  List<dynamic> _notes = [];
  bool _isLoading = true;
  bool _isOffline = false;
  String? _errorMessage;

  @override
  void initState() {
    super.initState();
    _loadNotes();
  }

  Future<void> _loadNotes() async {
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

    final result = await _api.fetchNotes();

    if (mounted) {
      setState(() {
        _isLoading = false;
        if (result['success'] == true) {
          _notes = List.from(result['notes'] ?? []);
          _isOffline = result['offline'] == true;
          _errorMessage = null;
        } else {
          _errorMessage = result['message'] ?? 'Failed to load notes';
          if (result['unpaired'] == true) {
            _errorMessage = 'Session expired. Please pair again.';
          }
        }
      });
    }
  }

  Future<void> _createNote() async {
    final result = await showDialog<Map<String, String>>(
      context: context,
      builder: (context) => const _CreateNoteDialog(),
    );

    if (result != null && mounted) {
      setState(() => _isLoading = true);

      final apiResult = await _api.createNote(
        result['title'] ?? 'Untitled',
        result['content'] ?? '',
      );

      if (mounted) {
        if (apiResult['success'] == true) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                apiResult['offline'] == true
                    ? 'Note saved for sync when online'
                    : 'Note created successfully',
              ),
              backgroundColor:
                  apiResult['offline'] == true ? Colors.orange : Colors.green,
            ),
          );
          await _loadNotes();
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(apiResult['message'] ?? 'Failed to create note'),
              backgroundColor: Colors.red,
            ),
          );
          setState(() => _isLoading = false);
        }
      }
    }
  }

  void _viewNote(Map<String, dynamic> note) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => _NoteDetailScreen(note: note),
      ),
    );
  }

  String _formatDate(String? dateStr) {
    if (dateStr == null || dateStr.isEmpty) return '';
    try {
      final date = DateTime.parse(dateStr);
      final now = DateTime.now();
      final today = DateTime(now.year, now.month, now.day);
      final noteDate = DateTime(date.year, date.month, date.day);

      if (noteDate == today) {
        return 'Today ${date.hour}:${date.minute.toString().padLeft(2, '0')}';
      } else if (noteDate == today.subtract(const Duration(days: 1))) {
        return 'Yesterday';
      }
      return '${date.day}/${date.month}/${date.year}';
    }
    catch (e) {
      return dateStr;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Notes'),
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
            onPressed: _loadNotes,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: _buildBody(),
      floatingActionButton: FloatingActionButton(
        onPressed: _createNote,
        backgroundColor: const Color(0xFFE85D04),
        child: const Icon(Icons.add),
      ),
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
                onPressed: _loadNotes,
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

    if (_notes.isEmpty) {
      return RefreshIndicator(
        onRefresh: _loadNotes,
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
                    Icons.note_outlined,
                    size: 64,
                    color: Colors.grey[600],
                  ),
                  const SizedBox(height: 16),
                  Text(
                    'No notes yet',
                    style: TextStyle(
                      fontSize: 18,
                      color: Colors.grey[500],
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'Tap + to create your first note',
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
      onRefresh: _loadNotes,
      color: const Color(0xFFE85D04),
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _notes.length,
        itemBuilder: (context, index) {
          final note = Map<String, dynamic>.from(_notes[index]);
          final title = note['title'] ?? 'Untitled';
          final content = note['content'] ?? '';
          final updatedAt = note['updated_at']?.toString();

          // Get preview of content (first ~100 chars)
          final preview = content.length > 100
              ? '${content.substring(0, 100)}...'
              : content;

          return Card(
            margin: const EdgeInsets.only(bottom: 12),
            color: const Color(0xFF16213E),
            child: InkWell(
              onTap: () => _viewNote(note),
              borderRadius: BorderRadius.circular(12),
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        const Icon(
                          Icons.note,
                          size: 18,
                          color: Color(0xFFE85D04),
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            title,
                            style: const TextStyle(
                              fontSize: 16,
                              fontWeight: FontWeight.w600,
                              color: Colors.white,
                            ),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                        ),
                        if (updatedAt != null)
                          Text(
                            _formatDate(updatedAt),
                            style: TextStyle(
                              fontSize: 12,
                              color: Colors.grey[500],
                            ),
                          ),
                      ],
                    ),
                    if (preview.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      Text(
                        preview,
                        maxLines: 3,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 14,
                          color: Colors.grey[400],
                          height: 1.4,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }
}

class _CreateNoteDialog extends StatefulWidget {
  const _CreateNoteDialog();

  @override
  State<_CreateNoteDialog> createState() => _CreateNoteDialogState();
}

class _CreateNoteDialogState extends State<_CreateNoteDialog> {
  final _titleController = TextEditingController();
  final _contentController = TextEditingController();

  @override
  void dispose() {
    _titleController.dispose();
    _contentController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      backgroundColor: const Color(0xFF16213E),
      title: const Text('New Note'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: _titleController,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: 'Title',
                hintStyle: TextStyle(color: Colors.grey[500]),
                filled: true,
                fillColor: const Color(0xFF1A1A2E),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: BorderSide.none,
                ),
              ),
              autofocus: true,
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _contentController,
              style: const TextStyle(color: Colors.white),
              maxLines: 6,
              decoration: InputDecoration(
                hintText: 'Write your note...',
                hintStyle: TextStyle(color: Colors.grey[500]),
                filled: true,
                fillColor: const Color(0xFF1A1A2E),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: BorderSide.none,
                ),
              ),
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        ElevatedButton(
          onPressed: () {
            final title = _titleController.text.trim();
            final content = _contentController.text.trim();
            if (title.isEmpty && content.isEmpty) {
              return;
            }
            Navigator.pop(context, {
              'title': title.isEmpty ? 'Untitled' : title,
              'content': content,
            });
          },
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFFE85D04),
          ),
          child: const Text('Create'),
        ),
      ],
    );
  }
}

class _NoteDetailScreen extends StatelessWidget {
  final Map<String, dynamic> note;

  const _NoteDetailScreen({required this.note});

  @override
  Widget build(BuildContext context) {
    final title = note['title'] ?? 'Untitled';
    final content = note['content'] ?? '';
    final updatedAt = note['updated_at']?.toString();

    String formattedDate = '';
    if (updatedAt != null) {
      try {
        final date = DateTime.parse(updatedAt);
        formattedDate =
            '${date.day}/${date.month}/${date.year} ${date.hour}:${date.minute.toString().padLeft(2, '0')}';
      }
      catch (e) {
        formattedDate = updatedAt;
      }
    }

    return Scaffold(
      appBar: AppBar(
        title: Text(
          title,
          style: const TextStyle(fontSize: 18),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (formattedDate.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Row(
                  children: [
                    Icon(
                      Icons.access_time,
                      size: 14,
                      color: Colors.grey[500],
                    ),
                    const SizedBox(width: 6),
                    Text(
                      'Last updated: $formattedDate',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey[500],
                      ),
                    ),
                  ],
                ),
              ),
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFF16213E),
                borderRadius: BorderRadius.circular(12),
              ),
              child: SelectableText(
                content.isEmpty ? 'No content' : content,
                style: TextStyle(
                  fontSize: 15,
                  color: content.isEmpty ? Colors.grey[500] : Colors.white,
                  height: 1.6,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
