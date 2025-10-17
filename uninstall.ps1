# Shakshuka Uninstaller Script
# Run as Administrator

param(
    [string]$InstallPath = "C:\Program Files\Shakshuka"
)

Write-Host "Uninstalling Shakshuka..." -ForegroundColor Yellow

# Stop any running instances
Write-Host "Stopping Shakshuka processes..." -ForegroundColor Cyan
Get-Process -Name "Shakshuka" -ErrorAction SilentlyContinue | Stop-Process -Force

# Wait a moment for processes to stop
Start-Sleep -Seconds 2

# Remove files
Write-Host "Removing application files..." -ForegroundColor Cyan
if (Test-Path "$InstallPath") {
    Remove-Item -Recurse -Force "$InstallPath"
    Write-Host "Removed: $InstallPath" -ForegroundColor Green
}

# Remove shortcuts
Write-Host "Removing shortcuts..." -ForegroundColor Cyan

$desktopShortcut = "$env:USERPROFILE\Desktop\Shakshuka.lnk"
if (Test-Path $desktopShortcut) {
    Remove-Item $desktopShortcut
    Write-Host "Removed desktop shortcut" -ForegroundColor Green
}

$startMenuShortcut = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Shakshuka"
if (Test-Path $startMenuShortcut) {
    Remove-Item -Recurse -Force $startMenuShortcut
    Write-Host "Removed Start Menu shortcuts" -ForegroundColor Green
}

# Remove registry entries
Write-Host "Removing registry entries..." -ForegroundColor Cyan
try {
    Remove-Item -Path "HKCU:\Software\Shakshuka" -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Removed registry entries" -ForegroundColor Green
} catch {
    Write-Warning "Could not remove registry entries: $_"
}

# Remove data directory (ask user)
$dataDir = "$env:USERPROFILE\AppData\Local\Shakshuka"
if (Test-Path $dataDir) {
    $response = Read-Host "Do you want to remove your Shakshuka data? (y/N)"
    if ($response -eq "y" -or $response -eq "Y") {
        Remove-Item -Recurse -Force $dataDir
        Write-Host "Removed user data" -ForegroundColor Green
    } else {
        Write-Host "User data preserved at: $dataDir" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Shakshuka uninstalled successfully!" -ForegroundColor Green
Write-Host "Thank you for using Shakshuka!" -ForegroundColor Cyan
