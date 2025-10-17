# Shakshuka v1.0.0 - Windows Distribution

## Quick Start

1. **Extract** this ZIP file to any folder
2. **Right-click** on `install.ps1` and select "Run with PowerShell" (as Administrator)
3. **Follow** the installation prompts
4. **Launch** Shakshuka from Desktop or Start Menu

## Easy Server Control

After installation, you can easily control the server:

### Method 1: Batch Files (Easiest)
- **Start**: Double-click `Start-Shakshuka.bat`
- **Stop**: Double-click `Stop-Shakshuka.bat`

### Method 2: PowerShell Scripts
```powershell
# Check status
.\server-manager.ps1 -Action status

# Start server
.\server-manager.ps1 -Action start

# Stop server
.\server-manager.ps1 -Action stop
```

### Method 3: Manual
```cmd
# Start
Shakshuka.exe

# Stop (in another command prompt)
taskkill /F /IM Shakshuka.exe
```

## What's Included

- **Shakshuka.exe**: Main application
- **install.ps1**: Automated installer
- **uninstall.ps1**: Automated uninstaller
- **server-manager.ps1**: PowerShell server control
- **Start-Shakshuka.bat**: Easy start script
- **Stop-Shakshuka.bat**: Easy stop script
- **INSTALLATION.md**: Detailed installation guide
- **static/**: Web assets
- **templates/**: HTML templates
- **data/**: Default data directory

## System Requirements

- Windows 10/11
- PowerShell 5.0+
- Internet connection (for initial setup)
- Administrator privileges (for installation)

## Troubleshooting

### Installation Issues
- Run PowerShell as Administrator
- Check Windows execution policy: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
- Ensure all files are extracted properly

### Server Control Issues
- Use `taskkill /F /IM Shakshuka.exe` to force stop
- Check if port 8989 is available
- Run as Administrator if needed

### Browser Issues
- Manually navigate to http://127.0.0.1:8989
- Check Windows Firewall settings
- Ensure default browser is set correctly

## Support

For issues or questions:
1. Check the console output for error messages
2. Review the INSTALLATION.md file
3. Try running as Administrator
4. Check Windows Event Viewer for system errors

## Version: 1.0.0
## Build Date: 2025-10-17
