# Shakshuka Quick Start Guide

## 🚀 Installation (2 minutes)

1. **Extract** the ZIP file
2. **Right-click** `install.ps1` → "Run with PowerShell" (as Administrator)
3. **Done!** Use the desktop shortcut to start

## 🎮 Server Control

### Super Easy (Recommended)
- **Start**: Double-click `Start-Shakshuka.bat`
- **Stop**: Double-click `Stop-Shakshuka.bat`

### PowerShell Way
```powershell
.\server-manager.ps1 -Action start   # Start
.\server-manager.ps1 -Action stop    # Stop
.\server-manager.ps1 -Action status  # Check
```

### Manual Way
```cmd
Shakshuka.exe                        # Start
taskkill /F /IM Shakshuka.exe        # Stop
```

## 🌐 Access

Once started, open your browser to:
**http://127.0.0.1:8989**

## ❓ Problems?

- **Won't start?** Run as Administrator
- **Won't stop?** Use `taskkill /F /IM Shakshuka.exe`
- **Browser won't open?** Go to http://127.0.0.1:8989 manually
- **Port busy?** Check if something else uses port 8989

## 🗑️ Uninstall

Right-click `uninstall.ps1` → "Run with PowerShell" (as Administrator)

---
**That's it! Enjoy using Shakshuka! 🎉**
