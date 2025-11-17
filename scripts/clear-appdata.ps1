# Clear Shakshuka AppData for Fresh PIN Setup
# This removes old authentication data to force PIN setup screen

param(
    [switch]$Force
)

Write-Host ""
Write-Host "====================================" -ForegroundColor Green
Write-Host "   Shakshuka AppData Cleaner" -ForegroundColor Green
Write-Host "====================================" -ForegroundColor Green
Write-Host ""

if (-not $Force) {
    Write-Host "This will delete old Shakshuka data from AppData" -ForegroundColor Yellow
    Write-Host "allowing you to test the PIN setup screen." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "WARNING: This will delete:" -ForegroundColor Red
    Write-Host " - Old login data"
    Write-Host " - Saved tasks"
    Write-Host " - Settings"
    Write-Host " - All user data"
    Write-Host ""
    
    $confirm = Read-Host "Are you sure you want to continue? (Y/N)"
    if ($confirm -ne 'Y' -and $confirm -ne 'y') {
        Write-Host ""
        Write-Host "Operation cancelled." -ForegroundColor Yellow
        exit 0
    }
}

Write-Host ""
Write-Host "Clearing AppData..." -ForegroundColor Cyan

# Stop Shakshuka if running
$process = Get-Process -Name "Shakshuka" -ErrorAction SilentlyContinue
if ($process) {
    Write-Host "Stopping Shakshuka..." -ForegroundColor Yellow
    Stop-Process -Name "Shakshuka" -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 2
}

# Clear AppData
$appdataDir = "$env:APPDATA\Shakshuka"
if (Test-Path $appdataDir) {
    Write-Host "Deleting: $appdataDir" -ForegroundColor Yellow
    try {
        Remove-Item -Path $appdataDir -Recurse -Force -ErrorAction Stop
        Write-Host "SUCCESS: AppData cleared" -ForegroundColor Green
    } catch {
        Write-Host "ERROR: Failed to delete AppData directory" -ForegroundColor Red
        Write-Host "Please close all Shakshuka windows and try again" -ForegroundColor Yellow
        exit 1
    }
} else {
    Write-Host "No AppData found - already clean" -ForegroundColor Green
}

# Clear LocalAppData
$localDir = "$env:LOCALAPPDATA\Shakshuka"
if (Test-Path $localDir) {
    Write-Host "Deleting: $localDir" -ForegroundColor Yellow
    Remove-Item -Path $localDir -Recurse -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "====================================" -ForegroundColor Green
Write-Host "   Cleanup Complete!" -ForegroundColor Green
Write-Host "====================================" -ForegroundColor Green
Write-Host ""
Write-Host "Next time you launch Shakshuka:" -ForegroundColor Cyan
Write-Host " - PIN setup screen will appear" -ForegroundColor White
Write-Host " - You'll create a new 4-digit PIN" -ForegroundColor White
Write-Host " - All data will be fresh" -ForegroundColor White
Write-Host ""

if (-not $Force) {
    Read-Host "Press Enter to exit"
}





