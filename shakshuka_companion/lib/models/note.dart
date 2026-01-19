import 'package:hive/hive.dart';
import 'package:uuid/uuid.dart';

part 'note.g.dart';

/// Local note model stored on the device and optionally synced to desktop.
@HiveType(typeId: 2)
class LocalNote extends HiveObject {
  @HiveField(0)
  String id;

  @HiveField(1)
  String title;

  @HiveField(2)
  String content;

  /// Creation timestamp, used for sorting and display.
  @HiveField(3)
  DateTime createdAt;

  LocalNote({
    String? id,
    required this.title,
    required this.content,
    DateTime? createdAt,
  })  : id = id ?? const Uuid().v4(),
        createdAt = createdAt ?? DateTime.now();

  /// JSON used when uploading notes to the desktop inbox API.
  Map<String, dynamic> toJson() => {
        'client_note_id': id,
        'title': title,
        'content': content,
        'created_at': createdAt.toIso8601String(),
      };
}
