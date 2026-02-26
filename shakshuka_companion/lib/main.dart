import 'package:flutter/material.dart';
import 'package:hive_flutter/hive_flutter.dart';
import 'package:workmanager/workmanager.dart';
import 'models/task.dart';
import 'models/note.dart';
import 'models/paired_device.dart';
import 'services/notification_service.dart';
import 'screens/home_screen.dart';

void callbackDispatcher() {
  Workmanager().executeTask((task, inputData) async {
    // This is the background task that will check for task status updates
    final notifications = NotificationService();
    await notifications.initialize();
    
    // Check for pending task status updates
    // We'll implement this logic in the notification service
    await notifications.checkTaskStatusUpdates();
    
    return Future.value(true);
  });
}

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  
  await Hive.initFlutter();
  Hive.registerAdapter(LocalTaskAdapter());
  Hive.registerAdapter(LocalNoteAdapter());
  Hive.registerAdapter(PairedDeviceAdapter());
  
  await Hive.openBox<LocalTask>('tasks');
  await Hive.openBox<LocalNote>('notes');
  await Hive.openBox<PairedDevice>('paired_device');
  
  // Initialize notifications
  await NotificationService().initialize();
  
  // Initialize background work for checking status updates
  await Workmanager().initialize(callbackDispatcher);
  
  // Register periodic task to check for updates every 15 minutes
  await Workmanager().registerPeriodicTask(
    'taskStatusCheck',
    'checkTaskStatus',
    frequency: const Duration(minutes: 15),
    constraints: Constraints(
      networkType: NetworkType.connected,
      requiresCharging: false,
    ),
  );
  
  final storage = StorageService();
  final initialTheme = await storage.getTheme();

  runApp(ShakshukaCompanionApp(initialTheme: initialTheme));
}

class ShakshukaCompanionApp extends StatefulWidget {
  final String initialTheme;
  const ShakshukaCompanionApp({super.key, required this.initialTheme});

  @override
  State<ShakshukaCompanionApp> createState() => _ShakshukaCompanionAppState();
}

class _ShakshukaCompanionAppState extends State<ShakshukaCompanionApp> {
  late String _themeName;

  @override
  void initState() {
    super.initState();
    _themeName = widget.initialTheme;
  }

  void _onThemeChanged(String theme) {
    setState(() {
      _themeName = theme;
    });
  }

  ThemeData _buildTheme(String name) {
    // Map to desktop themes: orange, dark (blue), self-esteem (mint), anxiety (sky), yellow.
    switch (name) {
      case 'dark':
        return ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF4A90E2),
            brightness: Brightness.dark,
          ),
          useMaterial3: true,
          scaffoldBackgroundColor: const Color(0xFF1A1A1A),
          appBarTheme: const AppBarTheme(
            backgroundColor: Color(0xFF151515),
            foregroundColor: Colors.white,
            elevation: 0,
          ),
          cardTheme: CardTheme(
            color: const Color(0xFF151515),
            elevation: 2,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          floatingActionButtonTheme: const FloatingActionButtonThemeData(
            backgroundColor: Color(0xFF4A90E2),
            foregroundColor: Colors.white,
          ),
        );
      case 'self-esteem':
        return ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF4ECDC4),
            brightness: Brightness.dark,
          ),
          useMaterial3: true,
          scaffoldBackgroundColor: const Color(0xFF10221F),
          appBarTheme: const AppBarTheme(
            backgroundColor: Color(0xFF10221F),
            foregroundColor: Colors.white,
            elevation: 0,
          ),
          cardTheme: CardTheme(
            color: const Color(0xFF132A26),
            elevation: 2,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          floatingActionButtonTheme: const FloatingActionButtonThemeData(
            backgroundColor: Color(0xFF4ECDC4),
            foregroundColor: Colors.white,
          ),
        );
      case 'anxiety':
        return ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFF74B9FF),
            brightness: Brightness.dark,
          ),
          useMaterial3: true,
          scaffoldBackgroundColor: const Color(0xFF102034),
          appBarTheme: const AppBarTheme(
            backgroundColor: Color(0xFF102034),
            foregroundColor: Colors.white,
            elevation: 0,
          ),
          cardTheme: CardTheme(
            color: const Color(0xFF182844),
            elevation: 2,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          floatingActionButtonTheme: const FloatingActionButtonThemeData(
            backgroundColor: Color(0xFF74B9FF),
            foregroundColor: Colors.white,
          ),
        );
      case 'yellow':
        return ThemeData(
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFFFFC107),
            brightness: Brightness.dark,
          ),
          useMaterial3: true,
          scaffoldBackgroundColor: const Color(0xFF201A09),
          appBarTheme: const AppBarTheme(
            backgroundColor: Color(0xFF201A09),
            foregroundColor: Colors.white,
            elevation: 0,
          ),
          cardTheme: CardTheme(
            color: const Color(0xFF261E0B),
            elevation: 2,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          floatingActionButtonTheme: const FloatingActionButtonThemeData(
            backgroundColor: Color(0xFFFFC107),
            foregroundColor: Colors.white,
          ),
        );
      case 'orange':
      default:
        return ThemeData(
          // Desktop orange accent is #FF8C42 (base-orange in theme.css)
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xFFFF8C42),
            brightness: Brightness.dark,
          ),
          useMaterial3: true,
          scaffoldBackgroundColor: const Color(0xFF1A1A2E),
          appBarTheme: const AppBarTheme(
            backgroundColor: Color(0xFF16213E),
            foregroundColor: Colors.white,
            elevation: 0,
          ),
          cardTheme: CardTheme(
            color: const Color(0xFF16213E),
            elevation: 2,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
          ),
          floatingActionButtonTheme: const FloatingActionButtonThemeData(
            backgroundColor: Color(0xFFE85D04),
            foregroundColor: Colors.white,
          ),
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Shakshuka Companion',
      debugShowCheckedModeBanner: false,
      theme: _buildTheme(_themeName),
      home: HomeScreen(
        onThemeChanged: _onThemeChanged,
      ),
    );
  }
}
