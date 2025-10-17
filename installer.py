#!/usr/bin/env python3
"""
Shakshuka Windows Installer
Creates a proper Windows installation with start menu shortcuts and uninstaller
"""

import os
import sys
import shutil
import subprocess
import winreg
from pathlib import Path
import json

class ShakshukaInstaller:
    def __init__(self):
        self.app_name = "Shakshuka"
        self.app_version = "1.0.0"
        self.install_dir = Path(os.environ['PROGRAMFILES']) / self.app_name
        self.start_menu_dir = Path(os.environ['APPDATA']) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / self.app_name
        self.desktop_dir = Path(os.environ['USERPROFILE']) / "Desktop"
        self.current_dir = Path(__file__).parent
        
    def create_installer_script(self):
        """Create a PowerShell installer script"""
        installer_script = f'''# Shakshuka Installer Script
# Run as Administrator

param(
    [string]$InstallPath = "{self.install_dir}",
    [switch]$Uninstall
)

if ($Uninstall) {{
    Write-Host "Uninstalling Shakshuka..." -ForegroundColor Yellow
    
    # Stop any running instances
    Get-Process -Name "Shakshuka" -ErrorAction SilentlyContinue | Stop-Process -Force
    
    # Remove files
    if (Test-Path "$InstallPath") {{
        Remove-Item -Recurse -Force "$InstallPath"
    }}
    
    # Remove shortcuts
    $desktopShortcut = "$env:USERPROFILE\\Desktop\\Shakshuka.lnk"
    if (Test-Path $desktopShortcut) {{
        Remove-Item $desktopShortcut
    }}
    
    $startMenuShortcut = "$env:APPDATA\\Microsoft\\Windows\\Start Menu\\Programs\\Shakshuka.lnk"
    if (Test-Path $startMenuShortcut) {{
        Remove-Item $startMenuShortcut
    }}
    
    # Remove registry entries
    try {{
        Remove-Item -Path "HKCU:\\Software\\Shakshuka" -Recurse -Force -ErrorAction SilentlyContinue
    }} catch {{}}
    
    Write-Host "Shakshuka uninstalled successfully!" -ForegroundColor Green
    exit 0
}}

Write-Host "Installing Shakshuka..." -ForegroundColor Green

# Create installation directory
if (-not (Test-Path "$InstallPath")) {{
    New-Item -ItemType Directory -Path "$InstallPath" -Force
}}

# Copy application files
$sourceDir = "{self.current_dir}"
$files = @(
    "Shakshuka.exe",
    "data",
    "static",
    "templates",
    "requirements.txt",
    "README.md"
)

foreach ($file in $files) {{
    $sourcePath = Join-Path $sourceDir $file
    $destPath = Join-Path $InstallPath $file
    
    if (Test-Path $sourcePath) {{
        if ((Get-Item $sourcePath) -is [System.IO.DirectoryInfo]) {{
            Copy-Item -Path $sourcePath -Destination $destPath -Recurse -Force
        }} else {{
            Copy-Item -Path $sourcePath -Destination $destPath -Force
        }}
        Write-Host "Copied: $file" -ForegroundColor Cyan
    }}
}}

# Create shortcuts
$shell = New-Object -ComObject WScript.Shell

# Desktop shortcut
$desktopShortcut = $shell.CreateShortcut("$env:USERPROFILE\\Desktop\\Shakshuka.lnk")
$desktopShortcut.TargetPath = "$InstallPath\\Shakshuka.exe"
$desktopShortcut.WorkingDirectory = "$InstallPath"
$desktopShortcut.Description = "Shakshuka Task Manager"
$desktopShortcut.IconLocation = "$InstallPath\\static\\images\\icon.ico"
$desktopShortcut.Save()

# Start Menu shortcut
$startMenuDir = "$env:APPDATA\\Microsoft\\Windows\\Start Menu\\Programs"
if (-not (Test-Path "$startMenuDir\\Shakshuka")) {{
    New-Item -ItemType Directory -Path "$startMenuDir\\Shakshuka" -Force
}}

$startMenuShortcut = $shell.CreateShortcut("$startMenuDir\\Shakshuka\\Shakshuka.lnk")
$startMenuShortcut.TargetPath = "$InstallPath\\Shakshuka.exe"
$startMenuShortcut.WorkingDirectory = "$InstallPath"
$startMenuShortcut.Description = "Shakshuka Task Manager"
$startMenuShortcut.IconLocation = "$InstallPath\\static\\images\\icon.ico"
$startMenuShortcut.Save()

# Uninstaller shortcut
$uninstallShortcut = $shell.CreateShortcut("$startMenuDir\\Shakshuka\\Uninstall Shakshuka.lnk")
$uninstallShortcut.TargetPath = "powershell.exe"
$uninstallShortcut.Arguments = "-ExecutionPolicy Bypass -File `"$InstallPath\\uninstall.ps1`" -Uninstall"
$uninstallShortcut.Description = "Uninstall Shakshuka"
$uninstallShortcut.Save()

# Create registry entries
try {{
    $regPath = "HKCU:\\Software\\Shakshuka"
    if (-not (Test-Path $regPath)) {{
        New-Item -Path $regPath -Force
    }}
    Set-ItemProperty -Path $regPath -Name "InstallPath" -Value "$InstallPath"
    Set-ItemProperty -Path $regPath -Name "Version" -Value "{self.app_version}"
    Set-ItemProperty -Path $regPath -Name "InstallDate" -Value (Get-Date -Format "yyyy-MM-dd")
}} catch {{
    Write-Warning "Could not create registry entries: $_"
}}

Write-Host "Shakshuka installed successfully!" -ForegroundColor Green
Write-Host "Installation path: $InstallPath" -ForegroundColor Cyan
Write-Host "Desktop shortcut created" -ForegroundColor Cyan
Write-Host "Start Menu shortcut created" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can now run Shakshuka from the Desktop or Start Menu" -ForegroundColor Yellow
Write-Host "To uninstall, run: .\\uninstall.ps1 -Uninstall" -ForegroundColor Yellow
'''
        
        with open("install.ps1", "w", encoding="utf-8") as f:
            f.write(installer_script)
        
        print("Created install.ps1")
    
    def create_uninstaller_script(self):
        """Create an uninstaller script"""
        uninstaller_script = f'''# Shakshuka Uninstaller Script
# Run as Administrator

param(
    [string]$InstallPath = "{self.install_dir}"
)

Write-Host "Uninstalling Shakshuka..." -ForegroundColor Yellow

# Stop any running instances
Write-Host "Stopping Shakshuka processes..." -ForegroundColor Cyan
Get-Process -Name "Shakshuka" -ErrorAction SilentlyContinue | Stop-Process -Force

# Wait a moment for processes to stop
Start-Sleep -Seconds 2

# Remove files
Write-Host "Removing application files..." -ForegroundColor Cyan
if (Test-Path "$InstallPath") {{
    Remove-Item -Recurse -Force "$InstallPath"
    Write-Host "Removed: $InstallPath" -ForegroundColor Green
}}

# Remove shortcuts
Write-Host "Removing shortcuts..." -ForegroundColor Cyan

$desktopShortcut = "$env:USERPROFILE\\Desktop\\Shakshuka.lnk"
if (Test-Path $desktopShortcut) {{
    Remove-Item $desktopShortcut
    Write-Host "Removed desktop shortcut" -ForegroundColor Green
}}

$startMenuShortcut = "$env:APPDATA\\Microsoft\\Windows\\Start Menu\\Programs\\Shakshuka"
if (Test-Path $startMenuShortcut) {{
    Remove-Item -Recurse -Force $startMenuShortcut
    Write-Host "Removed Start Menu shortcuts" -ForegroundColor Green
}}

# Remove registry entries
Write-Host "Removing registry entries..." -ForegroundColor Cyan
try {{
    Remove-Item -Path "HKCU:\\Software\\Shakshuka" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Removed registry entries" -ForegroundColor Green
}} catch {{
    Write-Warning "Could not remove registry entries: $_"
}}

# Remove data directory (ask user)
$dataDir = "$env:USERPROFILE\\AppData\\Local\\Shakshuka"
if (Test-Path $dataDir) {{
    $response = Read-Host "Do you want to remove your Shakshuka data? (y/N)"
    if ($response -eq "y" -or $response -eq "Y") {{
        Remove-Item -Recurse -Force $dataDir
        Write-Host "Removed user data" -ForegroundColor Green
    }} else {{
        Write-Host "User data preserved at: $dataDir" -ForegroundColor Yellow
    }}
}}

Write-Host ""
Write-Host "Shakshuka uninstalled successfully!" -ForegroundColor Green
Write-Host "Thank you for using Shakshuka!" -ForegroundColor Cyan
'''
        
        with open("uninstall.ps1", "w", encoding="utf-8") as f:
            f.write(uninstaller_script)
        
        print("Created uninstall.ps1")
    
    def create_server_manager(self):
        """Create a server management script"""
        server_manager = '''# Shakshuka Server Manager
# Provides easy server control for users

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("start", "stop", "restart", "status")]
    [string]$Action
)

$appName = "Shakshuka"
$processName = "Shakshuka"

function Get-ServerStatus {
    $processes = Get-Process -Name $processName -ErrorAction SilentlyContinue
    if ($processes) {
        Write-Host "Shakshuka is running (PID: $($processes.Id))" -ForegroundColor Green
        return $true
    } else {
        Write-Host "Shakshuka is not running" -ForegroundColor Red
        return $false
    }
}

function Start-Server {
    $isRunning = Get-ServerStatus
    if ($isRunning) {
        Write-Host "Shakshuka is already running!" -ForegroundColor Yellow
        return
    }
    
    # Try to find Shakshuka.exe
    $possiblePaths = @(
        "$env:USERPROFILE\\Desktop\\Shakshuka.exe",
        "$env:PROGRAMFILES\\Shakshuka\\Shakshuka.exe",
        "Shakshuka.exe"
    )
    
    $exePath = $null
    foreach ($path in $possiblePaths) {
        if (Test-Path $path) {
            $exePath = $path
            break
        }
    }
    
    if (-not $exePath) {
        Write-Host "Could not find Shakshuka.exe" -ForegroundColor Red
        Write-Host "Please ensure Shakshuka is installed" -ForegroundColor Red
        return
    }
    
    Write-Host "Starting Shakshuka..." -ForegroundColor Cyan
    Start-Process -FilePath $exePath -WindowStyle Normal
    Start-Sleep -Seconds 2
    
    if (Get-ServerStatus) {
        Write-Host "Shakshuka started successfully!" -ForegroundColor Green
        Write-Host "The application should open in your browser at http://127.0.0.1:8989" -ForegroundColor Cyan
    } else {
        Write-Host "Failed to start Shakshuka" -ForegroundColor Red
    }
}

function Stop-Server {
    $isRunning = Get-ServerStatus
    if (-not $isRunning) {
        Write-Host "Shakshuka is not running" -ForegroundColor Yellow
        return
    }
    
    Write-Host "Stopping Shakshuka..." -ForegroundColor Cyan
    Get-Process -Name $processName -ErrorAction SilentlyContinue | Stop-Process -Force
    
    Start-Sleep -Seconds 2
    
    if (-not (Get-ServerStatus)) {
        Write-Host "Shakshuka stopped successfully!" -ForegroundColor Green
    } else {
        Write-Host "Failed to stop Shakshuka. You may need to run as Administrator." -ForegroundColor Red
    }
}

function Restart-Server {
    Write-Host "Restarting Shakshuka..." -ForegroundColor Cyan
    Stop-Server
    Start-Sleep -Seconds 1
    Start-Server
}

# Main execution
switch ($Action) {
    "start" { Start-Server }
    "stop" { Stop-Server }
    "restart" { Restart-Server }
    "status" { Get-ServerStatus }
}

Write-Host ""
Write-Host "Usage examples:" -ForegroundColor Yellow
Write-Host "  .\\server-manager.ps1 -Action start" -ForegroundColor White
Write-Host "  .\\server-manager.ps1 -Action stop" -ForegroundColor White
Write-Host "  .\\server-manager.ps1 -Action restart" -ForegroundColor White
Write-Host "  .\\server-manager.ps1 -Action status" -ForegroundColor White
'''
        
        with open("server-manager.ps1", "w", encoding="utf-8") as f:
            f.write(server_manager)
        
        print("Created server-manager.ps1")
    
    def create_batch_files(self):
        """Create convenient batch files for users"""
        
        # Start Shakshuka batch file
        start_batch = '''@echo off
title Shakshuka Server Manager
echo Starting Shakshuka...
echo.

REM Try to find Shakshuka.exe
if exist "%USERPROFILE%\\Desktop\\Shakshuka.exe" (
    set "SHAKSHUKA_PATH=%USERPROFILE%\\Desktop\\Shakshuka.exe"
) else if exist "%PROGRAMFILES%\\Shakshuka\\Shakshuka.exe" (
    set "SHAKSHUKA_PATH=%PROGRAMFILES%\\Shakshuka\\Shakshuka.exe"
) else if exist "Shakshuka.exe" (
    set "SHAKSHUKA_PATH=Shakshuka.exe"
) else (
    echo ERROR: Could not find Shakshuka.exe
    echo Please ensure Shakshuka is installed
    pause
    exit /b 1
)

echo Found Shakshuka at: %SHAKSHUKA_PATH%
echo Starting server...
echo.
echo The application will open in your browser at http://127.0.0.1:8989
echo Press Ctrl+C to stop the server
echo.

start "" "%SHAKSHUKA_PATH%"
'''
        
        with open("Start-Shakshuka.bat", "w", encoding="utf-8") as f:
            f.write(start_batch)
        
        # Stop Shakshuka batch file
        stop_batch = '''@echo off
title Shakshuka Server Manager
echo Stopping Shakshuka...
echo.

tasklist /FI "IMAGENAME eq Shakshuka.exe" 2>NUL | find /I /N "Shakshuka.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo Found running Shakshuka processes
    taskkill /F /IM Shakshuka.exe
    echo Shakshuka stopped successfully!
) else (
    echo No Shakshuka processes found
)

echo.
pause
'''
        
        with open("Stop-Shakshuka.bat", "w", encoding="utf-8") as f:
            f.write(stop_batch)
        
        print("Created Start-Shakshuka.bat and Stop-Shakshuka.bat")
    
    def create_readme(self):
        """Create installation README"""
        readme_content = f'''# Shakshuka Installation Guide

## Quick Installation

1. **Run as Administrator**: Right-click on `install.ps1` and select "Run with PowerShell"
2. **Follow the prompts**: The installer will guide you through the process
3. **Launch**: Use the desktop shortcut or Start Menu to run Shakshuka

## Manual Installation

If you prefer manual installation:

1. Copy all files to `{self.install_dir}`
2. Create shortcuts pointing to `Shakshuka.exe`
3. Run `Shakshuka.exe` to start the application

## Server Management

### Easy Control (Recommended)
- **Start**: Double-click `Start-Shakshuka.bat`
- **Stop**: Double-click `Stop-Shakshuka.bat`

### PowerShell Control
```powershell
# Check status
.\\server-manager.ps1 -Action status

# Start server
.\\server-manager.ps1 -Action start

# Stop server
.\\server-manager.ps1 -Action stop

# Restart server
.\\server-manager.ps1 -Action restart
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

## Version: {self.app_version}
'''
        
        with open("INSTALLATION.md", "w", encoding="utf-8") as f:
            f.write(readme_content)
        
        print("Created INSTALLATION.md")

def main():
    installer = ShakshukaInstaller()
    
    print("Creating Shakshuka Windows Distribution Package...")
    print("=" * 50)
    
    installer.create_installer_script()
    installer.create_uninstaller_script()
    installer.create_server_manager()
    installer.create_batch_files()
    installer.create_readme()
    
    print("=" * 50)
    print("Distribution package created successfully!")
    print("")
    print("Files created:")
    print("- install.ps1 (PowerShell installer)")
    print("- uninstall.ps1 (PowerShell uninstaller)")
    print("- server-manager.ps1 (Server control)")
    print("- Start-Shakshuka.bat (Easy start)")
    print("- Stop-Shakshuka.bat (Easy stop)")
    print("- INSTALLATION.md (Installation guide)")
    print("")
    print("To distribute:")
    print("1. Zip all files including Shakshuka.exe")
    print("2. Users should run install.ps1 as Administrator")
    print("3. They can use the batch files for easy server control")

if __name__ == "__main__":
    main()