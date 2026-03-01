import 'package:flutter/material.dart';
import 'package:uuid/uuid.dart';
import '../services/api_service.dart';
import '../services/storage_service.dart';
import '../models/note.dart';

class NotesScreen extends StatefulWidget {
  const NotesScreen({super.key});

  @override
  State<NotesScreen> createState() => _NotesScreenState();
}

class _NotesScreenState extends State<NotesScreen> {
  final ApiService _api = ApiService();
  final StorageService _storage = StorageService();
  List<dynamic> _pcNotes = [];  // Notes from PC
  List<LocalNote> _localNotes = [];  // Notes stored locally waiting to be sent
  bool _isLoading = true;
  bool _isOffline = false;
  String? _errorMessage;
  final Uuid _uuid = const Uuid();

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

    // Load local notes
    _localNotes = await _storage.getAllNotes();

    // If paired, also load PC notes
    if (_storage.isPaired) {
      final result = await _api.fetchNotes();

      if (mounted) {
        setState(() {
          _isLoading = false;
          if (result['success'] == true) {
            _pcNotes = List.from(result['notes'] ?? []);
            _isOffline = result['offline'] == true;
            _errorMessage = null;
          } else {
            _errorMessage = result['message'] ?? 'Failed to load PC notes';
            if (result['unpaired'] == true) {
              _errorMessage = 'Session expired. Please pair again.';
            }
          }
        });
      }
    } else {
      setState(() {
        _isLoading = false;
        _pcNotes = [];
      });
    }
  }

  Future<void> _createNote() async {
    // Build folder list from both PC notes (including cached offline) and
    // local notes so the dropdown mirrors desktop's Notes Explorer.
    final Set<String> folderSet = {};
    for (final dynamic raw in _pcNotes) {
      try {
        final map = Map<String, dynamic>.from(raw as Map);
        final f = (map['folder'] ?? '').toString().trim();
        if (f.isNotEmpty) folderSet.add(f);
      } catch (_) {}
    }
    for (final LocalNote note in _localNotes) {
      final f = note.folder?.trim();
      if (f != null && f.isNotEmpty) folderSet.add(f);
    }
    final folders = folderSet.toList()
      ..sort((a, b) => a.toLowerCase().compareTo(b.toLowerCase()));

    final result = await showDialog<Map<String, String>>(
      context: context,
      builder: (context) => _CreateNoteDialog(availableFolders: folders),
    );

    if (result != null && mounted) {
      final folderRaw = (result['folder'] ?? '').trim();
      final folder = folderRaw.isEmpty ? null : folderRaw;

      // Save note locally instead of creating directly on PC
      final note = LocalNote(
        id: _uuid.v4(),
        title: result['title'] ?? 'Untitled',
        content: result['content'] ?? '',
        createdAt: DateTime.now(),
        folder: folder,
      );

      await _storage.addNote(note);

      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Note saved locally. Use "Send to PC" to send it.'),
            backgroundColor: Colors.green,
          ),
        );
        await _loadNotes();
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

  void _viewLocalNote(LocalNote note) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => _LocalNoteDetailScreen(
          note: note,
          onDelete: () async {
            await _storage.deleteNote(note.id);
            if (mounted) {
              Navigator.pop(context);
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(
                  content: Text('Note deleted'),
                  backgroundColor: Colors.red,
                ),
              );
              await _loadNotes();
            }
          },
        ),
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
        title: Row(
          children: [
            const Text('Notes'),
            if (_localNotes.isNotEmpty) ...[
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                decoration: BoxDecoration(
                  color: const Color(0xFFE85D04),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  '${_localNotes.length} local',
                  style: const TextStyle(fontSize: 11),
                ),
              ),
            ],
          ],
        ),
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

    if (_localNotes.isEmpty && _pcNotes.isEmpty) {
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
        itemCount: _localNotes.length + _pcNotes.length,
        itemBuilder: (context, index) {
          // Show local notes first, then PC notes
          final isLocal = index < _localNotes.length;
          
          if (isLocal) {
            final note = _localNotes[index];
            final preview = note.content.length > 100
                ? '${note.content.substring(0, 100)}...'
                : note.content;

            return Card(
              margin: const EdgeInsets.only(bottom: 12),
              color: const Color(0xFF16213E),
              child: InkWell(
                onTap: () => _viewLocalNote(note),
                borderRadius: BorderRadius.circular(12),
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          const Icon(
                            Icons.phone_android,
                            size: 18,
                            color: Color(0xFFE85D04),
                          ),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              note.title,
                              style: const TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w600,
                                color: Colors.white,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                            decoration: BoxDecoration(
                              color: const Color(0xFFE85D04),
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: const Text(
                              'LOCAL',
                              style: TextStyle(fontSize: 9, fontWeight: FontWeight.bold),
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
          } else {
            final pcIndex = index - _localNotes.length;
            final note = Map<String, dynamic>.from(_pcNotes[pcIndex]);
            final title = note['title'] ?? 'Untitled';
            final content = note['content'] ?? '';
            final updatedAt = note['updated_at']?.toString();

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
                            Icons.computer,
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
          }
        },
      ),
    );
  }
}

class _CreateNoteDialog extends StatefulWidget {
  final List<String> availableFolders;

  const _CreateNoteDialog({this.availableFolders = const []});

  @override
  State<_CreateNoteDialog> createState() => _CreateNoteDialogState();
}

class _CreateNoteDialogState extends State<_CreateNoteDialog> {
  final _titleController = TextEditingController();
  final _contentController = TextEditingController();
  String? _selectedFolder;
  final TextEditingController _folderController = TextEditingController();

  @override
  void dispose() {
    _titleController.dispose();
    _contentController.dispose();
    _folderController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final folders = widget.availableFolders;

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
            Align(
              alignment: Alignment.centerLeft,
              child: Text(
                'Folder (optional)',
                style: TextStyle(color: Colors.grey[300], fontSize: 12),
              ),
            ),
            const SizedBox(height: 4),
            if (folders.isNotEmpty)
              DropdownButtonFormField<String?>(
                value: _selectedFolder,
                dropdownColor: const Color(0xFF1A1A2E),
                decoration: InputDecoration(
                  filled: true,
                  fillColor: const Color(0xFF1A1A2E),
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(10),
                    borderSide: BorderSide.none,
                  ),
                  contentPadding:
                      const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                ),
                hint: Text('Select folder',
                    style: TextStyle(color: Colors.grey[500])),
                items: [
                  const DropdownMenuItem<String?>(
                    value: null,
                    child: Text('No folder'),
                  ),
                  ...folders.map((f) => DropdownMenuItem<String?>(
                        value: f,
                        child: Text(f),
                      )),
                ],
                onChanged: (value) {
                  setState(() {
                    _selectedFolder = value;
                  });
                },
              ),
            if (folders.isNotEmpty) const SizedBox(height: 8),
            TextField(
              controller: _folderController,
              style: const TextStyle(color: Colors.white),
              decoration: InputDecoration(
                hintText: folders.isNotEmpty
                    ? 'Or type a new folder name'
                    : 'Folder name',
                hintStyle: TextStyle(color: Colors.grey[500]),
                filled: true,
                fillColor: const Color(0xFF1A1A2E),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(10),
                  borderSide: BorderSide.none,
                ),
              ),
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
            final typedFolder = _folderController.text.trim();
            final folder = typedFolder.isNotEmpty
                ? typedFolder
                : (_selectedFolder != null ? _selectedFolder!.trim() : '');
            if (title.isEmpty && content.isEmpty) {
              return;
            }
            Navigator.pop(context, {
              'title': title.isEmpty ? 'Untitled' : title,
              'content': content,
              'folder': folder,
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

class _LocalNoteDetailScreen extends StatelessWidget {
  final LocalNote note;
  final VoidCallback onDelete;

  const _LocalNoteDetailScreen({required this.note, required this.onDelete});

  @override
  Widget build(BuildContext context) {
    final formattedDate =
        '${note.createdAt.day}/${note.createdAt.month}/${note.createdAt.year} ${note.createdAt.hour}:${note.createdAt.minute.toString().padLeft(2, '0')}';

    return Scaffold(
      appBar: AppBar(
        title: Text(
          note.title,
          style: const TextStyle(fontSize: 18),
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.delete, color: Colors.red),
            onPressed: () {
              showDialog(
                context: context,
                builder: (context) => AlertDialog(
                  backgroundColor: const Color(0xFF16213E),
                  title: const Text('Delete Note'),
                  content: const Text(
                    'Are you sure you want to delete this local note?',
                  ),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('Cancel'),
                    ),
                    ElevatedButton(
                      onPressed: () {
                        Navigator.pop(context);
                        onDelete();
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.red,
                      ),
                      child: const Text('Delete'),
                    ),
                  ],
                ),
              );
            },
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFFE85D04),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: const Text(
                  'LOCAL NOTE - NOT YET SENT TO PC',
                  style: TextStyle(fontSize: 10, fontWeight: FontWeight.bold),
                ),
              ),
            ),
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
                    'Created: $formattedDate',
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
                note.content.isEmpty ? 'No content' : note.content,
                style: TextStyle(
                  fontSize: 15,
                  color: note.content.isEmpty ? Colors.grey[500] : Colors.white,
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
