# Script to remove console.log statements from app.js
# Replaces with Utils.Logger where appropriate

$appJsPath = "C:\Users\vibin\OneDrive\Desktop\shakshuka-python-final3\assets\static\js\app.js"
$content = Get-Content $appJsPath -Raw

# Replace console.log with Utils.Logger.info
$content = $content -replace "console\.log\('Shakshuka", "Utils.Logger.info('Shakshuka"
$content = $content -replace "console\.log\('Loading", "Utils.Logger.info('Loading"
$content = $content -replace "console\.log\('Performing", "Utils.Logger.info('Performing"
$content = $content -replace "console\.log\('Resetting", "Utils.Logger.info('Resetting"
$content = $content -replace "console\.log\('Daily", "Utils.Logger.info('Daily"

# Replace console.error with Utils.Logger.error
$content = $content -replace "console\.error\(", "Utils.Logger.error("

# Remove debug console.logs (simple ones)
$content = $content -replace "^\s*console\.log\([^)]*\);\s*$", "", "Multiline"

# Save cleaned version
Set-Content -Path $appJsPath -Value $content -NoNewline

Write-Host "Console.log statements cleaned up in app.js"
Write-Host "Backup saved as app.js.backup"
