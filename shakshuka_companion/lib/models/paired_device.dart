import 'package:hive/hive.dart';

part 'paired_device.g.dart';

@HiveType(typeId: 1)
class PairedDevice extends HiveObject {
  @HiveField(0)
  String serverUrl;

  @HiveField(1)
  String token;

  @HiveField(2)
  String deviceName;

  @HiveField(3)
  DateTime pairedAt;

  PairedDevice({
    required this.serverUrl,
    required this.token,
    required this.deviceName,
    DateTime? pairedAt,
  }) : pairedAt = pairedAt ?? DateTime.now();

  String get displayUrl {
    final uri = Uri.parse(serverUrl);
    return '${uri.host}:${uri.port}';
  }
}
