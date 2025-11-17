# Shakshuka Server Manager
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
        "$env:USERPROFILE\Desktop\Shakshuka.exe",
        "$env:PROGRAMFILES\Shakshuka\Shakshuka.exe",
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
Write-Host "  .\server-manager.ps1 -Action start" -ForegroundColor White
Write-Host "  .\server-manager.ps1 -Action stop" -ForegroundColor White
Write-Host "  .\server-manager.ps1 -Action restart" -ForegroundColor White
Write-Host "  .\server-manager.ps1 -Action status" -ForegroundColor White
