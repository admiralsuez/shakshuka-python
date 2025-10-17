#!/usr/bin/env python3
"""
Shakshuka Distribution Packager
Creates a complete distribution package for Windows
"""

import os
import shutil
import zipfile
from pathlib import Path
import subprocess
import sys

class ShakshukaDistributor:
    def __init__(self):
        self.project_dir = Path(__file__).parent
        self.dist_dir = self.project_dir / "dist-package"
        self.version = "1.0.0"
        
    def create_distribution_package(self):
        """Create a complete distribution package"""
        print("Creating Shakshuka Distribution Package...")
        print("=" * 50)
        
        # Clean and create dist directory
        if self.dist_dir.exists():
            shutil.rmtree(self.dist_dir)
        self.dist_dir.mkdir()
        
        # Files to include in distribution
        files_to_copy = [
            "Shakshuka.exe",
            "install.ps1",
            "uninstall.ps1", 
            "server-manager.ps1",
            "Start-Shakshuka.bat",
            "Stop-Shakshuka.bat",
            "INSTALLATION.md",
            "README.md",
            "requirements.txt"
        ]
        
        # Directories to include
        dirs_to_copy = [
            "static",
            "templates",
            "data"
        ]
        
        print("Copying files...")
        for file_name in files_to_copy:
            src = self.project_dir / file_name
            if src.exists():
                dst = self.dist_dir / file_name
                shutil.copy2(src, dst)
                print(f"[OK] {file_name}")
            else:
                print(f"[MISSING] {file_name} (not found)")
        
        print("\nCopying directories...")
        for dir_name in dirs_to_copy:
            src = self.project_dir / dir_name
            if src.exists():
                dst = self.dist_dir / dir_name
                shutil.copytree(src, dst)
                print(f"[OK] {dir_name}/")
            else:
                print(f"[MISSING] {dir_name}/ (not found)")
        
        # Create additional distribution files
        self.create_distribution_readme()
        self.create_quick_start_guide()
        
        print("\n" + "=" * 50)
        print("Distribution package created successfully!")
        print(f"Location: {self.dist_dir}")
        
        # Create ZIP file
        self.create_zip_package()
        
    def create_distribution_readme(self):
        """Create a distribution README"""
        readme_content = f'''# Shakshuka v{self.version} - Windows Distribution

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
.\\server-manager.ps1 -Action status

# Start server
.\\server-manager.ps1 -Action start

# Stop server
.\\server-manager.ps1 -Action stop
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

## Version: {self.version}
## Build Date: {self.get_build_date()}
'''
        
        readme_path = self.dist_dir / "README-DISTRIBUTION.md"
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(readme_content)
        
        print("[OK] README-DISTRIBUTION.md")
    
    def create_quick_start_guide(self):
        """Create a quick start guide"""
        quick_start = '''# Shakshuka Quick Start Guide

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
.\\server-manager.ps1 -Action start   # Start
.\\server-manager.ps1 -Action stop    # Stop
.\\server-manager.ps1 -Action status  # Check
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
'''
        
        quick_start_path = self.dist_dir / "QUICK-START.md"
        with open(quick_start_path, "w", encoding="utf-8") as f:
            f.write(quick_start)
        
        print("[OK] QUICK-START.md")
    
    def create_zip_package(self):
        """Create a ZIP package for distribution"""
        zip_name = f"Shakshuka-v{self.version}-Windows.zip"
        zip_path = self.project_dir / zip_name
        
        print(f"\nCreating ZIP package: {zip_name}")
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(self.dist_dir):
                for file in files:
                    file_path = Path(root) / file
                    arc_path = file_path.relative_to(self.dist_dir)
                    zipf.write(file_path, arc_path)
                    print(f"  [OK] {arc_path}")
        
        print(f"\nZIP package created: {zip_path}")
        print(f"Size: {zip_path.stat().st_size / 1024 / 1024:.1f} MB")
    
    def get_build_date(self):
        """Get current date for build info"""
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")
    
    def create_portable_version(self):
        """Create a portable version that doesn't require installation"""
        portable_dir = self.dist_dir / "portable"
        portable_dir.mkdir()
        
        # Copy main files
        shutil.copy2(self.project_dir / "Shakshuka.exe", portable_dir / "Shakshuka.exe")
        shutil.copytree(self.project_dir / "static", portable_dir / "static")
        shutil.copytree(self.project_dir / "templates", portable_dir / "templates")
        
        # Create portable launcher
        portable_launcher = '''@echo off
title Shakshuka Portable
echo Starting Shakshuka Portable...
echo.

REM Check if Shakshuka.exe exists
if not exist "Shakshuka.exe" (
    echo ERROR: Shakshuka.exe not found!
    echo Please ensure all files are extracted properly.
    pause
    exit /b 1
)

echo Starting server...
echo The application will open in your browser at http://127.0.0.1:8989
echo Press Ctrl+C to stop the server
echo.

start "" "Shakshuka.exe"
'''
        
        with open(portable_dir / "Start-Shakshuka-Portable.bat", "w") as f:
            f.write(portable_launcher)
        
        # Create portable README
        portable_readme = '''# Shakshuka Portable Version

## Usage

1. **Extract** all files to any folder
2. **Double-click** `Start-Shakshuka-Portable.bat`
3. **Open** your browser to http://127.0.0.1:8989

## Stop Server

Press `Ctrl+C` in the command window, or:
```cmd
taskkill /F /IM Shakshuka.exe
```

## Portable Benefits

- No installation required
- Runs from any folder
- No registry changes
- Easy to remove (just delete folder)

## Note

This portable version stores data in the same folder as the executable.
Make sure to backup your data folder if you have important tasks!
'''
        
        with open(portable_dir / "README-PORTABLE.md", "w") as f:
            f.write(portable_readme)
        
        print("[OK] Portable version created")

def main():
    distributor = ShakshukaDistributor()
    
    try:
        distributor.create_distribution_package()
        distributor.create_portable_version()
        
        print("\n" + "=" * 50)
        print("Distribution package ready!")
        print("\nFiles created:")
        print(f"- Shakshuka-v{distributor.version}-Windows.zip (Full installer)")
        print("- dist-package/ (Extracted files)")
        print("- dist-package/portable/ (Portable version)")
        print("\nTo distribute:")
        print("1. Share the ZIP file")
        print("2. Users extract and run install.ps1 as Administrator")
        print("3. Or use the portable version for no-install usage")
        
    except Exception as e:
        print(f"Error creating distribution: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
