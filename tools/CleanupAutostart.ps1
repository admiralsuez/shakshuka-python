# Cleanup legacy Shakshuka autostart entries
# This script removes old/duplicate autostart registrations, keeping only the VBS launcher
# Run with: powershell -ExecutionPolicy Bypass -File CleanupAutostart.ps1

param(
    [switch]$DryRun = $false
)

$AppName = "Shakshuka"
$VBSLauncher = "wscript.exe `"C:\Program Files\Shakshuka\Start-Shakshuka-Silent.vbs`""
$ErrorCount = 0
$CleanedCount = 0

function Log {
    param([string]$Message, [string]$Level = "INFO")
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$timestamp] [$Level] $Message"
}

function Remove-RegistryValue {
    param([string]$Path, [string]$Name)
    
    try {
        $key = Get-Item -Path $Path -ErrorAction SilentlyContinue
        if ($key -and (Get-ItemProperty -Path $Path -Name $Name -ErrorAction SilentlyContinue)) {
            if ($DryRun) {
                Log "Would remove: $Path\$Name" "DRY-RUN"
            } else {
                Remove-ItemProperty -Path $Path -Name $Name -Force
                Log "Removed: $Path\$Name" "CLEANED"
            }
            return $true
        }
    } catch {
        Log "Error removing registry value: $_" "ERROR"
        $ErrorCount++
    }
    return $false
}

function Remove-StartupShortcut {
    param([string]$Path)
    
    try {
        if (Test-Path $Path) {
            if ($DryRun) {
                Log "Would delete: $Path" "DRY-RUN"
            } else {
                Remove-Item -Path $Path -Force
                Log "Deleted shortcut: $Path" "CLEANED"
            }
            return $true
        }
    } catch {
        Log "Error removing shortcut: $_" "ERROR"
        $ErrorCount++
    }
    return $false
}

function Remove-ScheduledTask {
    param([string]$TaskName)
    
    try {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($task) {
            if ($DryRun) {
                Log "Would unregister task: $TaskName" "DRY-RUN"
            } else {
                Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
                Log "Unregistered scheduled task: $TaskName" "CLEANED"
            }
            return $true
        }
    } catch {
        Log "Error removing scheduled task: $_" "ERROR"
        $ErrorCount++
    }
    return $false
}

function Ensure-VBSLauncher {
    param([string]$RegistryPath)
    
    try {
        $currentValue = (Get-ItemProperty -Path $RegistryPath -Name $AppName -ErrorAction SilentlyContinue).$AppName
        
        if ($currentValue -eq $VBSLauncher) {
            Log "VBS launcher already registered correctly" "OK"
            return $true
        }
        
        if ($currentValue) {
            Log "Updating autostart from: $currentValue" "INFO"
            Log "                     to: $VBSLauncher" "INFO"
            
            if ($DryRun) {
                Log "Would update registry value" "DRY-RUN"
            } else {
                Set-ItemProperty -Path $RegistryPath -Name $AppName -Value $VBSLauncher
                Log "Updated autostart to VBS launcher" "CLEANED"
            }
            return $true
        } else {
            Log "No existing autostart entry; setting VBS launcher" "INFO"
            if (!$DryRun) {
                New-Item -Path $RegistryPath -Force -ErrorAction SilentlyContinue | Out-Null
                Set-ItemProperty -Path $RegistryPath -Name $AppName -Value $VBSLauncher
                Log "Set autostart to VBS launcher" "CLEANED"
            }
            return $true
        }
    } catch {
        Log "Error ensuring VBS launcher: $_" "ERROR"
        $ErrorCount++
        return $false
    }
}

# Main cleanup logic
Log "Starting Shakshuka autostart cleanup..." "INFO"
if ($DryRun) {
    Log "DRY RUN MODE - no changes will be made" "INFO"
}
Log ""

# 1. Clean up registry entries
Log "=== Registry Cleanup ===" "INFO"
$hkcuRunPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Run"
$hklmRunPath = "HKLM:\Software\Microsoft\Windows\CurrentVersion\Run"
$hklmRun32Path = "HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Run"

# Check and update/remove HKCU entries
if (Test-Path $hkcuRunPath) {
    $hkcuItems = Get-ItemProperty -Path $hkcuRunPath -ErrorAction SilentlyContinue
    foreach ($item in $hkcuItems.PSObject.Properties) {
        if ($item.Name -like "*Shakshuka*" -or $item.Value -like "*Shakshuka*") {
            if ($item.Name -eq $AppName -and $item.Value -eq $VBSLauncher) {
                Log "HKCU entry already correct: $($item.Value)" "OK"
            } else {
                Log "Found old HKCU entry: $($item.Name) = $($item.Value)" "WARN"
                Remove-RegistryValue -Path $hkcuRunPath -Name $item.Name
            }
        }
    }
}

# Ensure HKCU has the correct VBS launcher
Ensure-VBSLauncher -RegistryPath $hkcuRunPath

# Remove any HKLM entries (should only be in HKCU for current user)
if (Test-Path $hklmRunPath) {
    $hklmItems = Get-ItemProperty -Path $hklmRunPath -ErrorAction SilentlyContinue
    foreach ($item in $hklmItems.PSObject.Properties) {
        if ($item.Name -like "*Shakshuka*" -or $item.Value -like "*Shakshuka*") {
            Log "Found HKLM entry (should be HKCU only): $($item.Name) = $($item.Value)" "WARN"
            Remove-RegistryValue -Path $hklmRunPath -Name $item.Name
        }
    }
}

# Remove any 32-bit registry entries
if (Test-Path $hklmRun32Path) {
    $hklm32Items = Get-ItemProperty -Path $hklmRun32Path -ErrorAction SilentlyContinue
    foreach ($item in $hklm32Items.PSObject.Properties) {
        if ($item.Name -like "*Shakshuka*" -or $item.Value -like "*Shakshuka*") {
            Log "Found HKLM 32-bit entry: $($item.Name) = $($item.Value)" "WARN"
            Remove-RegistryValue -Path $hklmRun32Path -Name $item.Name
        }
    }
}

Log ""

# 2. Clean up Startup folder shortcuts
Log "=== Startup Folder Cleanup ===" "INFO"
$userStartupPath = "$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup"
$commonStartupPath = "$env:ProgramData\Microsoft\Windows\Start Menu\Programs\Startup"

if (Test-Path $userStartupPath) {
    $shortcuts = Get-ChildItem -Path $userStartupPath -Filter "*Shak*" -ErrorAction SilentlyContinue
    foreach ($shortcut in $shortcuts) {
        Log "Found shortcut in user Startup: $($shortcut.Name)" "WARN"
        Remove-StartupShortcut -Path $shortcut.FullName
    }
}

if (Test-Path $commonStartupPath) {
    $shortcuts = Get-ChildItem -Path $commonStartupPath -Filter "*Shak*" -ErrorAction SilentlyContinue
    foreach ($shortcut in $shortcuts) {
        Log "Found shortcut in common Startup: $($shortcut.Name)" "WARN"
        Remove-StartupShortcut -Path $shortcut.FullName
    }
}

Log ""

# 3. Clean up Scheduled Tasks
Log "=== Scheduled Task Cleanup ===" "INFO"
$tasks = Get-ScheduledTask -ErrorAction SilentlyContinue | Where-Object { $_.TaskName -like "*Shak*" -or ($_.Actions.Execute -like "*Shakshuka*") }
foreach ($task in $tasks) {
    Log "Found scheduled task: $($task.TaskName)" "WARN"
    Remove-ScheduledTask -TaskName $task.TaskName
}

Log ""
Log "=== Cleanup Complete ===" "INFO"
Log "Errors: $ErrorCount" "SUMMARY"

if ($DryRun) {
    Log "DRY RUN COMPLETE - To apply changes, run: powershell -ExecutionPolicy Bypass -File CleanupAutostart.ps1" "INFO"
} else {
    Log "Cleanup applied successfully" "SUMMARY"
}

exit $ErrorCount
