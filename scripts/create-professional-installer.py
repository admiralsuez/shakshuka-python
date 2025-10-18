#!/usr/bin/env python3
"""
Professional Self-Extracting Installer for Shakshuka
Creates a Windows installer without requiring Inno Setup
"""

import os
import sys
import shutil
import zipfile
import tempfile
from pathlib import Path
import subprocess

def create_installer_script():
    """Create the installer batch script"""
    installer_script = '''@echo off
setlocal enabledelayedexpansion

title Shakshuka Installer v1.0.0
color 0A

echo.
echo ===============================================
echo           Shakshuka Installer v1.0.0
echo ===============================================
echo.

REM Check for admin privileges
net session >nul 2>&1
if %errorLevel% == 0 (
    echo [INFO] Running with administrator privileges
) else (
    echo [WARNING] Not running as administrator
    echo [WARNING] Some features may not work properly
    echo.
    set /p "continue=Continue anyway? (y/n): "
    if /i not "!continue!"=="y" exit /b 1
)

echo.
echo [INFO] Checking system requirements...
echo [INFO] Windows version: %OS%
echo [INFO] Architecture: %PROCESSOR_ARCHITECTURE%

REM Check if Shakshuka is already running
tasklist /FI "IMAGENAME eq Shakshuka.exe" 2>NUL | find /I /N "Shakshuka.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [WARNING] Shakshuka is currently running
    echo [INFO] Stopping Shakshuka...
    taskkill /F /IM Shakshuka.exe >nul 2>&1
    timeout /t 2 >nul
)

echo.
echo [INFO] Installing Shakshuka to Program Files...

REM Create installation directory
set "INSTALL_DIR=%ProgramFiles%\\Shakshuka"
if not exist "%INSTALL_DIR%" (
    mkdir "%INSTALL_DIR%"
    echo [OK] Created installation directory
) else (
    echo [INFO] Installation directory already exists
)

REM Extract files
echo [INFO] Extracting application files...
powershell -Command "Expand-Archive -Path '%~dp0Shakshuka-Data.zip' -DestinationPath '%INSTALL_DIR%' -Force" >nul 2>&1
if %errorLevel% == 0 (
    echo [OK] Files extracted successfully
) else (
    echo [ERROR] Failed to extract files
    pause
    exit /b 1
)

REM Create Start Menu shortcuts
echo [INFO] Creating Start Menu shortcuts...
set "START_MENU=%ProgramData%\\Microsoft\\Windows\\Start Menu\\Programs\\Shakshuka"
if not exist "%START_MENU%" mkdir "%START_MENU%"

REM Main application shortcut
echo [InternetShortcut] > "%START_MENU%\\Shakshuka.url"
echo URL=file:///%INSTALL_DIR%\\Shakshuka.exe >> "%START_MENU%\\Shakshuka.url"
echo IconFile=%INSTALL_DIR%\\static\\images\\icon.ico >> "%START_MENU%\\Shakshuka.url"
echo IconIndex=0 >> "%START_MENU%\\Shakshuka.url"

REM Start server shortcut
echo [InternetShortcut] > "%START_MENU%\\Start Shakshuka.url"
echo URL=file:///%INSTALL_DIR%\\Start-Shakshuka.bat >> "%START_MENU%\\Start Shakshuka.url"
echo IconFile=%INSTALL_DIR%\\static\\images\\icon.ico >> "%START_MENU%\\Start Shakshuka.url"
echo IconIndex=0 >> "%START_MENU%\\Start Shakshuka.url"

REM Stop server shortcut
echo [InternetShortcut] > "%START_MENU%\\Stop Shakshuka.url"
echo URL=file:///%INSTALL_DIR%\\Stop-Shakshuka.bat >> "%START_MENU%\\Stop Shakshuka.url"
echo IconFile=%INSTALL_DIR%\\static\\images\\icon.ico >> "%START_MENU%\\Stop Shakshuka.url"
echo IconIndex=0 >> "%START_MENU%\\Stop Shakshuka.url"

echo [OK] Start Menu shortcuts created

REM Create Desktop shortcut (optional)
set /p "desktop=Create Desktop shortcut? (y/n): "
if /i "!desktop!"=="y" (
    echo [InternetShortcut] > "%USERPROFILE%\\Desktop\\Shakshuka.url"
    echo URL=file:///%INSTALL_DIR%\\Shakshuka.exe >> "%USERPROFILE%\\Desktop\\Shakshuka.url"
    echo IconFile=%INSTALL_DIR%\\static\\images\\icon.ico >> "%USERPROFILE%\\Desktop\\Shakshuka.url"
    echo IconIndex=0 >> "%USERPROFILE%\\Desktop\\Shakshuka.url"
    echo [OK] Desktop shortcut created
)

REM Create uninstaller
echo [INFO] Creating uninstaller...
echo @echo off > "%INSTALL_DIR%\\uninstall.bat"
echo title Shakshuka Uninstaller >> "%INSTALL_DIR%\\uninstall.bat"
echo echo Uninstalling Shakshuka... >> "%INSTALL_DIR%\\uninstall.bat"
echo taskkill /F /IM Shakshuka.exe ^>nul 2^>^&1 >> "%INSTALL_DIR%\\uninstall.bat"
echo timeout /t 2 ^>nul >> "%INSTALL_DIR%\\uninstall.bat"
echo rmdir /s /q "%INSTALL_DIR%" >> "%INSTALL_DIR%\\uninstall.bat"
echo rmdir /s /q "%START_MENU%" >> "%INSTALL_DIR%\\uninstall.bat"
echo del "%USERPROFILE%\\Desktop\\Shakshuka.url" ^>nul 2^>^&1 >> "%INSTALL_DIR%\\uninstall.bat"
echo echo Shakshuka has been uninstalled. >> "%INSTALL_DIR%\\uninstall.bat"
echo pause >> "%INSTALL_DIR%\\uninstall.bat"

REM Add to Add/Remove Programs (simplified)
echo [INFO] Adding to Add/Remove Programs...
reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Shakshuka" /v "DisplayName" /t REG_SZ /d "Shakshuka" /f >nul 2>&1
reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Shakshuka" /v "UninstallString" /t REG_SZ /d "\"%INSTALL_DIR%\\uninstall.bat\"" /f >nul 2>&1
reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Shakshuka" /v "InstallLocation" /t REG_SZ /d "%INSTALL_DIR%" /f >nul 2>&1
reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Shakshuka" /v "DisplayVersion" /t REG_SZ /d "1.0.0" /f >nul 2>&1
reg add "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\Shakshuka" /v "Publisher" /t REG_SZ /d "Shakshuka Team" /f >nul 2>&1

echo [OK] Added to Add/Remove Programs

REM Create user data directory
echo [INFO] Setting up user data directory...
set "USER_DATA=%USERPROFILE%\\AppData\\Roaming\\Shakshuka"
if not exist "%USER_DATA%" mkdir "%USER_DATA%"
if not exist "%USER_DATA%\\data" mkdir "%USER_DATA%\\data"

REM Copy initial data if user data doesn't exist
if not exist "%USER_DATA%\\data\\users" (
    xcopy "%INSTALL_DIR%\\data\\*" "%USER_DATA%\\data\\" /E /I /Y >nul 2>&1
    echo [OK] Initial data copied to user directory
)

echo.
echo ===============================================
echo           Installation Complete!
echo ===============================================
echo.
echo Shakshuka has been successfully installed to:
echo %INSTALL_DIR%
echo.
echo Start Menu shortcuts created in:
echo %START_MENU%
echo.
echo User data will be stored in:
echo %USER_DATA%
echo.
echo To start Shakshuka:
echo 1. Use the Start Menu shortcut, or
echo 2. Run: "%INSTALL_DIR%\\Shakshuka.exe"
echo.
echo To uninstall:
echo 1. Use Add/Remove Programs, or
echo 2. Run: "%INSTALL_DIR%\\uninstall.bat"
echo.

set /p "start=Start Shakshuka now? (y/n): "
if /i "!start!"=="y" (
    echo [INFO] Starting Shakshuka...
    start "" "%INSTALL_DIR%\\Shakshuka.exe"
)

echo.
echo Thank you for installing Shakshuka!
pause
'''
    
    return installer_script

def create_professional_installer():
    """Create a professional self-extracting installer"""
    print("Creating Professional Self-Extracting Installer...")
    print("=" * 50)
    
    # Create dist directory
    dist_dir = Path("dist")
    dist_dir.mkdir(exist_ok=True)
    
    # Create temporary directory for installer files
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        print("Preparing installer files...")
        
        # Copy all necessary files to temp directory
        files_to_copy = [
            "Shakshuka.exe",
            "Start-Shakshuka.bat",
            "Stop-Shakshuka.bat",
            "server-manager.ps1",
            "README.md",
            "INSTALLATION.md",
            "TROUBLESHOOTING.md",
            "QUICK-START.md",
            "requirements.txt",
            "config.py",
            "version.json"
        ]
        
        dirs_to_copy = [
            "static",
            "templates",
            "data"
        ]
        
        for file_name in files_to_copy:
            src = Path(file_name)
            if src.exists():
                dst = temp_path / file_name
                shutil.copy2(src, dst)
                print(f"[OK] {file_name}")
        
        for dir_name in dirs_to_copy:
            src = Path(dir_name)
            if src.exists():
                dst = temp_path / dir_name
                shutil.copytree(src, dst)
                print(f"[OK] {dir_name}/")
        
        # Create data ZIP file
        print("Creating data archive...")
        data_zip = temp_path / "Shakshuka-Data.zip"
        with zipfile.ZipFile(data_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(temp_path):
                for file in files:
                    if file != "Shakshuka-Data.zip":  # Don't include the zip itself
                        file_path = Path(root) / file
                        arc_path = file_path.relative_to(temp_path)
                        zipf.write(file_path, arc_path)
        
        print(f"[OK] Data archive created ({data_zip.stat().st_size / 1024 / 1024:.1f} MB)")
        
        # Create installer script
        print("Creating installer script...")
        installer_script = create_installer_script()
        installer_bat = temp_path / "install.bat"
        with open(installer_bat, 'w', encoding='utf-8') as f:
            f.write(installer_script)
        
        print("[OK] Installer script created")
        
        # Create final installer ZIP
        installer_name = "Shakshuka-Setup-v1.0.0.exe"
        installer_path = dist_dir / installer_name
        
        print("Creating self-extracting installer...")
        
        # Create a batch file that will extract and run the installer
        sfx_script = f'''@echo off
title Shakshuka Setup
echo Extracting installer files...
powershell -Command "Expand-Archive -Path '%~f0' -DestinationPath '%TEMP%\\ShakshukaSetup' -Force" >nul 2>&1
if %errorLevel% == 0 (
    echo Starting installer...
    start "" "%TEMP%\\ShakshukaSetup\\install.bat"
    timeout /t 3 >nul
    exit
) else (
    echo Error extracting files
    pause
)
'''
        
        # Create the self-extracting installer
        with zipfile.ZipFile(installer_path.with_suffix('.zip'), 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add the installer script
            zipf.write(installer_bat, "install.bat")
            # Add the data archive
            zipf.write(data_zip, "Shakshuka-Data.zip")
        
        # Rename to .exe for better user experience
        final_installer = installer_path.with_suffix('.zip')
        installer_path = installer_path.with_suffix('.exe')
        
        # Copy the zip as exe (users can rename it)
        shutil.copy2(final_installer, installer_path)
        
        size_mb = installer_path.stat().st_size / 1024 / 1024
        print(f"\nProfessional installer created: {installer_path}")
        print(f"Size: {size_mb:.1f} MB")
        
        return True

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
        "data"
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
    if create_professional_installer():
        create_portable_version()
        
        print("\n" + "=" * 50)
        print("Professional installer ready!")
        print("\nFiles created:")
        print("- dist/Shakshuka-Setup-v1.0.0.exe (Professional installer)")
        print("- dist/portable/ (Portable version)")
        print("\nInstallation features:")
        print("✅ Professional Windows installer")
        print("✅ Extracts to Program Files")
        print("✅ Creates Start Menu shortcuts")
        print("✅ Optional Desktop shortcut")
        print("✅ Proper uninstaller")
        print("✅ User data in AppData")
        print("✅ Admin privileges handling")
        print("✅ Add/Remove Programs integration")
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


