import 'package:hive/hive.dart';
import 'package:uuid/uuid.dart';

part 'task.g.dart';

@HiveType(typeId: 0)
class LocalTask extends HiveObject {
  @HiveField(0)
  String id;

  @HiveField(1)
  String title;

  @HiveField(2)
  String? description;

  @HiveField(3)
  int? duration; // in minutes

  @HiveField(4)
  String? dueDate; // YYYY-MM-DD

  @HiveField(5)
  DateTime createdAt;

  LocalTask({
    String? id,
    required this.title,
    this.description,
    this.duration,
    this.dueDate,
    DateTime? createdAt,
  })  : id = id ?? const Uuid().v4(),
        createdAt = createdAt ?? DateTime.now();

  Map<String, dynamic> toJson() => {
        'client_task_id': id,
        'title': title,
        'description': description ?? '',
        'duration': duration ?? 30,
        'due_date': dueDate,
      };
}
