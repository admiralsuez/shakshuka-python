# Shakshuka Installation Guide

## Quick Installation

1. **Run as Administrator**: Right-click on `install.ps1` and select "Run with PowerShell"
2. **Follow the prompts**: The installer will guide you through the process
3. **Launch**: Use the desktop shortcut or Start Menu to run Shakshuka

## Manual Installation

If you prefer manual installation:

1. Copy all files to `C:\Program Files\Shakshuka`
2. Create shortcuts pointing to `Shakshuka.exe`
3. Run `Shakshuka.exe` to start the application

## Server Management

### Easy Control (Recommended)
- **Start**: Double-click `Start-Shakshuka.bat`
- **Stop**: Double-click `Stop-Shakshuka.bat`

### PowerShell Control
```powershell
# Check status
.\server-manager.ps1 -Action status

# Start server
.\server-manager.ps1 -Action start

# Stop server
.\server-manager.ps1 -Action stop

# Restart server
.\server-manager.ps1 -Action restart
```

### Manual Control
```cmd
# Start
Shakshuka.exe

# Stop (in another command prompt)
taskkill /F /IM Shakshuka.exe
```

## Uninstallation

1. **Easy**: Right-click on `uninstall.ps1` and select "Run with PowerShell"
2. **Manual**: Delete the installation folder and shortcuts

## Troubleshooting

### Server Won't Start
- Check if port 8989 is available
- Run as Administrator if needed
- Check Windows Firewall settings

### Server Won't Stop
- Use `taskkill /F /IM Shakshuka.exe` in Command Prompt
- Run as Administrator if needed
- Restart your computer if necessary

### Browser Won't Open
- Manually navigate to http://127.0.0.1:8989
- Check if your default browser is set correctly

## Support

If you encounter issues:
1. Check the console output for error messages
2. Ensure all files are present in the installation directory
3. Try running as Administrator
4. Check Windows Event Viewer for system errors

## Version: 1.0.0
