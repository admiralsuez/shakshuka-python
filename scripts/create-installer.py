#!/usr/bin/env python3
"""
Professional Installer Builder for Shakshuka
Creates a Windows installer using Inno Setup
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_inno_setup():
    """Check if Inno Setup is installed"""
    inno_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        r"C:\Program Files\Inno Setup 5\ISCC.exe"
    ]
    
    for path in inno_paths:
        if os.path.exists(path):
            return path
    
    return None

def install_inno_setup():
    """Download and install Inno Setup"""
    print("Inno Setup not found. Please install it manually:")
    print("1. Go to https://jrsoftware.org/isinfo.php")
    print("2. Download Inno Setup 6")
    print("3. Install it with default settings")
    print("4. Run this script again")
    return False

def create_installer():
    """Create the Windows installer"""
    print("Creating Professional Windows Installer...")
    print("=" * 50)
    
    # Check if Inno Setup is available
    inno_path = check_inno_setup()
    if not inno_path:
        return install_inno_setup()
    
    # Ensure dist directory exists
    dist_dir = Path("dist")
    dist_dir.mkdir(exist_ok=True)
    
    # Run Inno Setup compiler
    cmd = [inno_path, "installer.iss"]
    
    try:
        print("Compiling installer with Inno Setup...")
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Installer created successfully!")
        
        # Check if installer was created
        installer_path = dist_dir / "Shakshuka-Setup-v1.0.0.exe"
        if installer_path.exists():
            size_mb = installer_path.stat().st_size / 1024 / 1024
            print(f"\nInstaller created: {installer_path}")
            print(f"Size: {size_mb:.1f} MB")
            print("\nInstallation features:")
            print("✅ Professional Windows installer")
            print("✅ Extracts to Program Files")
            print("✅ Creates Start Menu shortcuts")
            print("✅ Optional Desktop shortcut")
            print("✅ Optional Quick Launch shortcut")
            print("✅ Optional Windows startup")
            print("✅ Proper uninstaller")
            print("✅ User data in AppData")
            print("✅ License agreement")
            print("✅ Admin privileges handling")
            return True
        else:
            print("Error: Installer file not found after compilation")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"Error creating installer: {e}")
        print(f"Error output: {e.stderr}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

def create_portable_version():
    """Create a portable version as backup"""
    print("\nCreating portable version as backup...")
    
    portable_dir = Path("dist/portable")
    portable_dir.mkdir(exist_ok=True)
    
    # Copy files for portable version
    files_to_copy = [
        "Shakshuka.exe",
        "Start-Shakshuka.bat",
        "Stop-Shakshuka.bat",
        "README.md",
        "TROUBLESHOOTING.md"
    ]
    
    dirs_to_copy = [
        "static",
        "templates",
        "data"
    ]
    
    for file_name in files_to_copy:
        src = Path(file_name)
        if src.exists():
            dst = portable_dir / file_name
            shutil.copy2(src, dst)
            print(f"[OK] {file_name}")
    
    for dir_name in dirs_to_copy:
        src = Path(dir_name)
        if src.exists():
            dst = portable_dir / dir_name
            shutil.copytree(src, dst, dirs_exist_ok=True)
            print(f"[OK] {dir_name}/")
    
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
    
    print("[OK] Portable version created")

def main():
    """Main build process"""
    print("Shakshuka Professional Installer Builder")
    print("=" * 50)
    
    # Check if we're on Windows
    if sys.platform != 'win32':
        print("Error: This installer builder is designed for Windows only.")
        return 1
    
    # Check if required files exist
    required_files = [
        "Shakshuka.exe",
        "static",
        "templates", 
        "data",
        "installer.iss",
        "LICENSE.txt"
    ]
    
    missing_files = []
    for file_name in required_files:
        if not Path(file_name).exists():
            missing_files.append(file_name)
    
    if missing_files:
        print("Error: Missing required files:")
        for file_name in missing_files:
            print(f"  - {file_name}")
        print("\nPlease run the build script first to create Shakshuka.exe")
        return 1
    
    # Create installer
    if create_installer():
        create_portable_version()
        
        print("\n" + "=" * 50)
        print("Professional installer ready!")
        print("\nFiles created:")
        print("- dist/Shakshuka-Setup-v1.0.0.exe (Professional installer)")
        print("- dist/portable/ (Portable version)")
        print("\nTo distribute:")
        print("1. Share the Shakshuka-Setup-v1.0.0.exe file")
        print("2. Users double-click to install like any professional software")
        print("3. Or use the portable version for no-install usage")
        
        return 0
    else:
        print("\nInstaller creation failed.")
        return 1

if __name__ == '__main__':
    sys.exit(main())


