# Shakshuka Companion

Shakshuka Companion - A Flutter companion app for Shakshuka Task Manager. Add tasks on your phone and sync them to your PC.

**Author**: vibinandvanshika

## Features

- **Offline task creation**: Add tasks anytime, even without network
- **QR code pairing**: Scan QR from PC to connect
- **Batch upload**: Send all tasks to PC with one tap
- **Auto-clear**: Tasks are cleared after successful upload

## Setup

### Prerequisites

1. Install [Flutter SDK](https://docs.flutter.dev/get-started/install)
2. Android SDK (via Android Studio)

### Build APK

```bash
cd shakshuka_companion

# Get dependencies
flutter pub get

# Build release APK
flutter build apk --release
```

The APK will be at: `build/app/outputs/flutter-apk/app-release.apk`

### Development

```bash
# Run on connected device
flutter run

# Run with hot reload
flutter run --debug
```

## Usage

1. Open Shakshuka on your PC
2. Go to **Settings** → **Pair Phone**
3. Note the 6-digit code shown
4. Open this app on your phone
5. Tap the link icon → Scan the QR code
6. Enter the 6-digit code
7. Add tasks on your phone
8. Tap "Send to PC" when ready

Tasks will appear in Shakshuka's inbox for approval.

## Permissions

- **Camera**: For QR code scanning
- **Internet**: To communicate with PC
