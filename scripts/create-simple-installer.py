#!/usr/bin/env python3
"""
Simple Windows Installer Creator for Shakshuka
Creates a basic batch-based installer for maximum compatibility
"""

import os
import shutil
import zipfile
from pathlib import Path
from datetime import datetime

def create_simple_installer():
    """Create a simple batch-based installer"""
    
    print("Shakshuka Simple Installer Creator")
    print("=" * 50)
    
    project_dir = Path(__file__).parent
    dist_dir = project_dir / "dist"
    installer_dir = dist_dir / "simple-installer"
    
    # Clean and create directories
    if installer_dir.exists():
        shutil.rmtree(installer_dir)
    installer_dir.mkdir(parents=True, exist_ok=True)
    
    print("Creating simple installer...")
    
    # Copy main executable
    shutil.copy2(project_dir / "Shakshuka.exe", installer_dir / "Shakshuka.exe")
    print("[OK] Shakshuka.exe")
    
    # Copy batch files
    shutil.copy2(project_dir / "Start-Shakshuka.bat", installer_dir / "Start-Shakshuka.bat")
    shutil.copy2(project_dir / "Stop-Shakshuka.bat", installer_dir / "Stop-Shakshuka.bat")
    print("[OK] Batch files")
    
    # Copy directories
    shutil.copytree(project_dir / "static", installer_dir / "static")
    shutil.copytree(project_dir / "templates", installer_dir / "templates")
    shutil.copytree(project_dir / "data", installer_dir / "data")
    print("[OK] Application directories")
    
    # Copy documentation
    docs = ["README.md", "INSTALLATION.md", "TROUBLESHOOTING.md"]
    for doc in docs:
        if (project_dir / doc).exists():
            shutil.copy2(project_dir / doc, installer_dir / doc)
            print(f"[OK] {doc}")
    
    # Create simple installer script
    install_script = installer_dir / "install.bat"
    with open(install_script, "w", encoding="utf-8") as f:
        f.write("""@echo off
setlocal

echo.
echo ==================================================
echo  Shakshuka Simple Installer v1.0.0
echo ==================================================
echo.

REM Check for administrator privileges
NET SESSION >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Requesting Administrator privileges...
    powershell -Command "Start-Process -FilePath '%~dpnx0' -Verb RunAs"
    exit /b
)

REM Define installation paths
set "INSTALL_DIR=%PROGRAMFILES%\\Shakshuka"
set "DESKTOP_LINK=%USERPROFILE%\\Desktop\\Shakshuka.lnk"

echo Installing to: %INSTALL_DIR%
echo.

REM Create installation directory
echo Creating installation directory...
md "%INSTALL_DIR%" >nul 2>&1
IF NOT EXIST "%INSTALL_DIR%" (
    echo ERROR: Could not create installation directory.
    echo Please run as Administrator.
    pause
    exit /b 1
)

REM Copy files
echo Copying application files...
xcopy "%~dp0*" "%INSTALL_DIR%\\" /E /I /Y >nul
IF %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to copy files.
    pause
    exit /b 1
)

REM Create desktop shortcut
set /p "CREATE_DESKTOP=Create Desktop shortcut? (Y/N): "
if /i "%CREATE_DESKTOP%"=="Y" (
    echo Creating Desktop shortcut...
    powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%DESKTOP_LINK%'); $s.TargetPath = '%INSTALL_DIR%\\Shakshuka.exe'; $s.Save()"
)

REM Create uninstaller
echo @echo off > "%INSTALL_DIR%\\uninstall.bat"
echo set "INSTALL_DIR=%INSTALL_DIR%" >> "%INSTALL_DIR%\\uninstall.bat"
echo set "DESKTOP_LINK=%DESKTOP_LINK%" >> "%INSTALL_DIR%\\uninstall.bat"
echo. >> "%INSTALL_DIR%\\uninstall.bat"
echo NET SESSION ^>nul 2^>^&1 >> "%INSTALL_DIR%\\uninstall.bat"
echo IF %%ERRORLEVEL%% NEQ 0 ( >> "%INSTALL_DIR%\\uninstall.bat"
echo     echo Requesting Administrator privileges for uninstallation... >> "%INSTALL_DIR%\\uninstall.bat"
echo     powershell -Command "Start-Process -FilePath '%%~dpnx0' -Verb RunAs" >> "%INSTALL_DIR%\\uninstall.bat"
echo     exit /b >> "%INSTALL_DIR%\\uninstall.bat"
echo ) >> "%INSTALL_DIR%\\uninstall.bat"
echo. >> "%INSTALL_DIR%\\uninstall.bat"
echo echo ================================================== >> "%INSTALL_DIR%\\uninstall.bat"
echo echo  Uninstalling Shakshuka >> "%INSTALL_DIR%\\uninstall.bat"
echo echo ================================================== >> "%INSTALL_DIR%\\uninstall.bat"
echo echo. >> "%INSTALL_DIR%\\uninstall.bat"
echo echo Removing application files... >> "%INSTALL_DIR%\\uninstall.bat"
echo rmdir /s /q "%%INSTALL_DIR%%" >> "%INSTALL_DIR%\\uninstall.bat"
echo echo Removing Desktop shortcut... >> "%INSTALL_DIR%\\uninstall.bat"
echo del "%%DESKTOP_LINK%%" >nul 2^>^&1 >> "%INSTALL_DIR%\\uninstall.bat"
echo echo Uninstallation complete. >> "%INSTALL_DIR%\\uninstall.bat"
echo pause >> "%INSTALL_DIR%\\uninstall.bat"

echo.
echo ==================================================
echo  Installation Complete!
echo  You can now run Shakshuka from:
echo  %INSTALL_DIR%\\Shakshuka.exe
echo ==================================================
echo.
pause
exit /b 0
""")
    
    print("[OK] Installer script created")
    
    # Create ZIP package
    zip_path = dist_dir / "Shakshuka-Simple-Installer-v1.0.0.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(installer_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(installer_dir)
                zipf.write(file_path, arcname)
    
    print(f"[OK] ZIP package created: {zip_path}")
    print(f"Size: {zip_path.stat().st_size / (1024*1024):.1f} MB")
    
    print("\n" + "=" * 50)
    print("Simple installer ready!")
    print("\nFiles created:")
    print(f"- {installer_dir}/ (Simple installer directory)")
    print(f"- {zip_path} (ZIP package)")
    print("\nInstallation features:")
    print("✅ Simple batch-based installer")
    print("✅ Extracts to Program Files")
    print("✅ Optional Desktop shortcut")
    print("✅ Basic uninstaller")
    print("✅ Maximum compatibility")
    print("\nTo distribute:")
    print("1. Share the ZIP file")
    print("2. Users extract and run install.bat")
    print("3. Simple and reliable installation")

if __name__ == "__main__":
    create_simple_installer()


