# Shakshuka Installation Guide

## 🚀 Quick Start (Recommended)

**Just run the exe file directly!**

1. **Download** the Shakshuka ZIP file
2. **Extract** all files to any folder
3. **Double-click** `Shakshuka.exe`
4. **Done!** The app opens in your browser at http://127.0.0.1:8989

## 📋 When to Use the Installer

The `install.ps1` installer is **optional** and only needed if you want:

- **Professional installation** to Program Files
- **Desktop shortcuts** created automatically
- **Start Menu** integration
- **Registry entries** for proper uninstall
- **System-wide** installation

## 🎯 Installation Methods

### Method 1: Direct Execution (Easiest)
```
1. Extract ZIP file
2. Double-click Shakshuka.exe
3. Use the app!
```

### Method 2: Professional Installation
```
1. Extract ZIP file
2. Right-click install.ps1 → "Run with PowerShell" (as Administrator)
3. Follow prompts
4. Use desktop shortcut or Start Menu
```

### Method 3: Portable Usage
```
1. Extract ZIP file
2. Double-click Start-Shakshuka-Portable.bat
3. No installation, runs from any folder
```

## 🛠️ Server Control

### Easy Control (Works with any method)
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

## 📁 File Structure

```
Shakshuka/
├── Shakshuka.exe              # Main application (just run this!)
├── Start-Shakshuka.bat       # Easy start
├── Stop-Shakshuka.bat        # Easy stop
├── install.ps1               # Optional installer
├── uninstall.ps1             # Uninstaller (if you used installer)
├── server-manager.ps1         # Server control
├── static/                   # Web assets
├── templates/                # HTML templates
└── data/                     # Your data (created automatically)
```

## 🔧 System Requirements

- Windows 10/11
- No additional software needed
- Port 8989 available
- Internet connection (for initial setup)

## ❓ Troubleshooting

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

## 🗑️ Uninstallation

### If you used the installer:
- Right-click `uninstall.ps1` → "Run with PowerShell" (as Administrator)

### If you just ran the exe:
- Delete the folder
- Optionally delete the `data/` folder to remove all data

## 💡 Pro Tips

- **Keep the command window open** - closing it stops the server
- **Data is auto-saved** in the `data/` folder
- **No installation required** - just run the exe!
- **Portable** - runs from any folder
- **Self-contained** - includes everything needed

## 🎉 That's It!

**Bottom line**: Just double-click `Shakshuka.exe` and you're ready to go!

## Version: 1.0.0
