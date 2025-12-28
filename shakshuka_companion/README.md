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

## Changelog

### Version 1.3.0 (2025-12-28)
- **Unpair Detection**: App now detects when device is unpaired from desktop and prompts to re-pair
- **Tasks Preserved**: When unpaired, your tasks remain saved locally - nothing is lost
- **Re-pair Dialog**: Friendly dialog with "Pair Now" button when unpaired state is detected

### Version 1.2.0 (2025-12-28)
- **Dismissable "Not Paired" Bar**: The announcement bar can now be dismissed with X button, reappears on next launch
- **Consistent APK Signing**: GitHub Actions now uses consistent keystore for updates without reinstall
- **Delete Confirmation**: Added confirmation dialog before deleting tasks
- **Pull-to-Refresh**: Refresh connection status and sync history by pulling down

### Version 1.1.0 (2025-12-27)
- **Local Notifications**: Get notified when tasks are uploaded or processed
- **Background Status Polling**: App checks task approval/rejection status in background
- **Notification Settings**: Toggle notifications on/off in drawer menu

### Version 1.0.0 (2025-12-24)
- Initial release
- QR code pairing with desktop
- Offline task creation
- Batch upload to PC
- Task submission history with status tracking
