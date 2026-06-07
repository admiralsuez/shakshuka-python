$ErrorActionPreference = 'Stop'

$ProjectRoot = Split-Path -Parent $PSScriptRoot
$InstallRoot = 'C:\Program Files\Shakshuka'

$files = @(
    'assets\templates\index.html',
    'assets\templates\partials\scripts.html',
    'assets\templates\partials\pages\tasks_page.html',
    'assets\templates\partials\pages\notes_page.html',
    'assets\templates\partials\pages\settings_page.html',
    'assets\static\js\core\state.js',
    'assets\static\js\features\settings.js',
    'assets\static\js\pages\tasks.js',
    'assets\static\js\app\ui-shell.js',
    'assets\static\js\pages\notes.js',
    'assets\static\js\app\app.js',
    'assets\static\js\app\backup-update.js',
    'assets\static\css\style.css',
    'assets\static\css\core\layout.css',
    'assets\static\css\core\responsive.css',
    'assets\static\css\core\responsive-mobile-first.css',
    'assets\static\css\layout\layout-shell.css',
    'assets\static\css\layout\desktop-layout.css',
    'assets\static\css\pages\settings-and-nav.css',
    'assets\static\css\components\task-cards.css'
)

$filesToDelete = @(
    'assets\static\js\modules\paranoid-mode.js',
    'assets\static\js\modules\notes-paranoid-mode.js',
    'assets\static\css\features\paranoid-mode.css',
    'assets\static\css\features\notes-paranoid-mode.css'
)

foreach ($file in $files) {
    $source = Join-Path $ProjectRoot $file
    $destination = Join-Path $InstallRoot $file
    if (!(Test-Path $source)) {
        throw "Missing source file: $source"
    }
    $destDir = Split-Path -Parent $destination
    if (!(Test-Path $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }
    Copy-Item -Path $source -Destination $destination -Force
    Write-Host "Updated $destination"
}

foreach ($file in $filesToDelete) {
    $target = Join-Path $InstallRoot $file
    if (Test-Path $target) {
        Remove-Item -Path $target -Force
        Write-Host "Deleted $target"
    }
}

Write-Host 'Installed assets updated. Restart Shakshuka and hard refresh the browser.'
