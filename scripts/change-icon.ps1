# Shakshuka Icon Changer Script
# Changes the application icon across all locations

param(
    [Parameter(Mandatory=$true, HelpMessage="Path to your new .ico file")]
    [string]$NewIconPath
)

Write-Host "`n" -NoNewline
Write-Host "================================================" -ForegroundColor Cyan
Write-Host "   Shakshuka Icon Changer" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Validate new icon exists
if (-not (Test-Path $NewIconPath)) {
    Write-Host "ERROR: Icon file not found at: $NewIconPath" -ForegroundColor Red
    Write-Host "Please provide a valid path to an .ico file" -ForegroundColor Yellow
    exit 1
}

# Check if it's an .ico file
$extension = [System.IO.Path]::GetExtension($NewIconPath)
if ($extension -ne ".ico") {
    Write-Host "WARNING: File is not .ico format ($extension)" -ForegroundColor Yellow
    Write-Host "The icon might not work correctly in all places" -ForegroundColor Yellow
    $continue = Read-Host "Continue anyway? (y/n)"
    if ($continue -ne "y") {
        Write-Host "Operation cancelled" -ForegroundColor Yellow
        exit 0
    }
}

# Get file info
$newIcon = Get-Item $NewIconPath
$iconSize = [math]::Round($newIcon.Length / 1KB, 2)
Write-Host "New icon: $($newIcon.Name) ($iconSize KB)" -ForegroundColor White

# Define target path
$targetPath = "assets\static\images\icon.ico"

# Check if target exists
if (-not (Test-Path $targetPath)) {
    Write-Host "ERROR: Target path not found: $targetPath" -ForegroundColor Red
    Write-Host "Are you running this from the project root?" -ForegroundColor Yellow
    exit 1
}

# Backup old icon
$timestamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$backupPath = "assets\static\images\icon_backup_$timestamp.ico"

Write-Host "`nBacking up old icon..." -ForegroundColor Yellow
Copy-Item $targetPath $backupPath -Force
Write-Host "  Saved to: $backupPath" -ForegroundColor Green

# Copy new icon
Write-Host "`nReplacing icon..." -ForegroundColor Yellow
Copy-Item $NewIconPath $targetPath -Force
Write-Host "  New icon copied successfully!" -ForegroundColor Green

# Verify HTML has favicon link
Write-Host "`nChecking HTML template..." -ForegroundColor Yellow
$htmlPath = "assets\templates\index.html"
if (Test-Path $htmlPath) {
    $htmlContent = Get-Content $htmlPath -Raw
    if ($htmlContent -like "*favicon*") {
        Write-Host "  Favicon link already exists" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: No favicon link found in HTML!" -ForegroundColor Red
        Write-Host "  The HTML should already be updated, but if not, add:" -ForegroundColor Yellow
        Write-Host '  <link rel="icon" type="image/x-icon" href="{{ url_for(''static'', filename=''images/icon.ico'') }}">' -ForegroundColor Gray
    }
} else {
    Write-Host "  WARNING: index.html not found" -ForegroundColor Red
}

# Success summary
Write-Host "`n" -NoNewline
Write-Host "================================================" -ForegroundColor Green
Write-Host "   Icon Changed Successfully!" -ForegroundColor Green
Write-Host "================================================" -ForegroundColor Green

Write-Host "`nIcon locations that will be updated:" -ForegroundColor Cyan
Write-Host "  Browser favicon (when rebuilt)" -ForegroundColor White
Write-Host "  Shakshuka.exe file icon (when rebuilt)" -ForegroundColor White
Write-Host "  Installer setup icon (when rebuilt)" -ForegroundColor White
Write-Host "  All Start Menu shortcuts (when reinstalled)" -ForegroundColor White
Write-Host "  Desktop shortcuts (when reinstalled)" -ForegroundColor White

Write-Host "`nNext Steps:" -ForegroundColor Cyan
Write-Host "  1. Rebuild the application:" -ForegroundColor White
Write-Host "     python scripts\build.py" -ForegroundColor Gray
Write-Host "`n  2. Test the new build:" -ForegroundColor White
Write-Host "     .\Shakshuka.exe" -ForegroundColor Gray
Write-Host "`n  3. Clear browser cache:" -ForegroundColor White
Write-Host "     Press Ctrl+Shift+Delete or Ctrl+F5" -ForegroundColor Gray
Write-Host "`n  4. Reinstall (optional) for shortcuts:" -ForegroundColor White
Write-Host "     .\Shakshuka-Setup-v1.5.0-bXX.exe" -ForegroundColor Gray

Write-Host "`nBackup saved at: $backupPath" -ForegroundColor Yellow
Write-Host ""



