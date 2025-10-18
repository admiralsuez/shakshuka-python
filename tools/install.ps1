# Shakshuka Installer Script
# Run as Administrator

param(
    [string]$InstallPath = "C:\Program Files\Shakshuka",
    [switch]$Uninstall
)

if ($Uninstall) {
    Write-Host "Uninstalling Shakshuka..." -ForegroundColor Yellow
    
    # Stop any running instances
    Get-Process -Name "Shakshuka" -ErrorAction SilentlyContinue | Stop-Process -Force
    
    # Remove files
    if (Test-Path "$InstallPath") {
        Remove-Item -Recurse -Force "$InstallPath"
    }
    
    # Remove shortcuts
    $desktopShortcut = "$env:USERPROFILE\Desktop\Shakshuka.lnk"
    if (Test-Path $desktopShortcut) {
        Remove-Item $desktopShortcut
    }
    
    $startMenuShortcut = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Shakshuka.lnk"
    if (Test-Path $startMenuShortcut) {
        Remove-Item $startMenuShortcut
    }
    
    # Remove registry entries
    try {
        Remove-Item -Path "HKCU:\Software\Shakshuka" -Recurse -Force -ErrorAction SilentlyContinue
    } catch {}
    
    Write-Host "Shakshuka uninstalled successfully!" -ForegroundColor Green
    exit 0
}

Write-Host "Installing Shakshuka..." -ForegroundColor Green

# Create installation directory
if (-not (Test-Path "$InstallPath")) {
    New-Item -ItemType Directory -Path "$InstallPath" -Force
}

# Copy application files
$sourceDir = "C:\Users\vibin\OneDrive\Desktop\shakshuka-python-beta"
$files = @(
    "Shakshuka.exe",
    "data",
    "static",
    "templates",
    "requirements.txt",
    "README.md"
)

foreach ($file in $files) {
    $sourcePath = Join-Path $sourceDir $file
    $destPath = Join-Path $InstallPath $file
    
    if (Test-Path $sourcePath) {
        if ((Get-Item $sourcePath) -is [System.IO.DirectoryInfo]) {
            Copy-Item -Path $sourcePath -Destination $destPath -Recurse -Force
        } else {
            Copy-Item -Path $sourcePath -Destination $destPath -Force
        }
        Write-Host "Copied: $file" -ForegroundColor Cyan
    }
}

# Create shortcuts
$shell = New-Object -ComObject WScript.Shell

# Desktop shortcut
$desktopShortcut = $shell.CreateShortcut("$env:USERPROFILE\Desktop\Shakshuka.lnk")
$desktopShortcut.TargetPath = "$InstallPath\Shakshuka.exe"
$desktopShortcut.WorkingDirectory = "$InstallPath"
$desktopShortcut.Description = "Shakshuka Task Manager"
$desktopShortcut.IconLocation = "$InstallPath\static\images\icon.ico"
$desktopShortcut.Save()

# Start Menu shortcut
$startMenuDir = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
if (-not (Test-Path "$startMenuDir\Shakshuka")) {
    New-Item -ItemType Directory -Path "$startMenuDir\Shakshuka" -Force
}

$startMenuShortcut = $shell.CreateShortcut("$startMenuDir\Shakshuka\Shakshuka.lnk")
$startMenuShortcut.TargetPath = "$InstallPath\Shakshuka.exe"
$startMenuShortcut.WorkingDirectory = "$InstallPath"
$startMenuShortcut.Description = "Shakshuka Task Manager"
$startMenuShortcut.IconLocation = "$InstallPath\static\images\icon.ico"
$startMenuShortcut.Save()

# Uninstaller shortcut
$uninstallShortcut = $shell.CreateShortcut("$startMenuDir\Shakshuka\Uninstall Shakshuka.lnk")
$uninstallShortcut.TargetPath = "powershell.exe"
$uninstallShortcut.Arguments = "-ExecutionPolicy Bypass -File `"$InstallPath\uninstall.ps1`" -Uninstall"
$uninstallShortcut.Description = "Uninstall Shakshuka"
$uninstallShortcut.Save()

# Create registry entries
try {
    $regPath = "HKCU:\Software\Shakshuka"
    if (-not (Test-Path $regPath)) {
        New-Item -Path $regPath -Force
    }
    Set-ItemProperty -Path $regPath -Name "InstallPath" -Value "$InstallPath"
    Set-ItemProperty -Path $regPath -Name "Version" -Value "1.0.0"
    Set-ItemProperty -Path $regPath -Name "InstallDate" -Value (Get-Date -Format "yyyy-MM-dd")
} catch {
    Write-Warning "Could not create registry entries: $_"
}

Write-Host "Shakshuka installed successfully!" -ForegroundColor Green
Write-Host "Installation path: $InstallPath" -ForegroundColor Cyan
Write-Host "Desktop shortcut created" -ForegroundColor Cyan
Write-Host "Start Menu shortcut created" -ForegroundColor Cyan
Write-Host ""
Write-Host "You can now run Shakshuka from the Desktop or Start Menu" -ForegroundColor Yellow
Write-Host "To uninstall, run: .\uninstall.ps1 -Uninstall" -ForegroundColor Yellow
