@echo off
REM Shakshuka v2.0.0 Clean Backup Restoration Script
REM This script restores the clean backup version

echo ================================================
echo Shakshuka v2.0.0 Clean Backup Restoration
echo ================================================
echo.

echo Checking if backup exists...
if not exist "Shakshuka-v2.0.0-Clean-Backup" (
    echo ERROR: Backup directory not found!
    echo Please ensure Shakshuka-v2.0.0-Clean-Backup exists in the current directory.
    pause
    exit /b 1
)

echo Backup found. Starting restoration...
echo.

echo Creating backup of current state...
if exist "CURRENT_STATE_BACKUP" (
    echo Removing old current state backup...
    rmdir /s /q "CURRENT_STATE_BACKUP"
)
mkdir "CURRENT_STATE_BACKUP"

echo Backing up current files...
if exist "main.py" copy "main.py" "CURRENT_STATE_BACKUP\"
if exist "Shakshuka.exe" copy "Shakshuka.exe" "CURRENT_STATE_BACKUP\"
if exist "Shakshuka-Setup-*.exe" copy "Shakshuka-Setup-*.exe" "CURRENT_STATE_BACKUP\"
if exist "src" xcopy "src" "CURRENT_STATE_BACKUP\src\" /e /i
if exist "assets" xcopy "assets" "CURRENT_STATE_BACKUP\assets\" /e /i
if exist "config" xcopy "config" "CURRENT_STATE_BACKUP\config\" /e /i
if exist "scripts" xcopy "scripts" "CURRENT_STATE_BACKUP\scripts\" /e /i

echo.
echo Restoring clean backup version...

REM Remove current directories (be careful!)
if exist "src" rmdir /s /q "src"
if exist "assets" rmdir /s /q "assets"
if exist "config" rmdir /s /q "config"
if exist "scripts" rmdir /s /q "scripts"
if exist "tests" rmdir /s /q "tests"
if exist "tools" rmdir /s /q "tools"
if exist "docs" rmdir /s /q "docs"
if exist "documentation" rmdir /s /q "documentation"
if exist "build_reports" rmdir /s /q "build_reports"

REM Copy from backup
xcopy "Shakshuka-v2.0.0-Clean-Backup\src" "src\" /e /i
xcopy "Shakshuka-v2.0.0-Clean-Backup\assets" "assets\" /e /i
xcopy "Shakshuka-v2.0.0-Clean-Backup\config" "config\" /e /i
xcopy "Shakshuka-v2.0.0-Clean-Backup\scripts" "scripts\" /e /i
xcopy "Shakshuka-v2.0.0-Clean-Backup\tests" "tests\" /e /i
xcopy "Shakshuka-v2.0.0-Clean-Backup\tools" "tools\" /e /i
xcopy "Shakshuka-v2.0.0-Clean-Backup\docs" "docs\" /e /i
xcopy "Shakshuka-v2.0.0-Clean-Backup\documentation" "documentation\" /e /i
xcopy "Shakshuka-v2.0.0-Clean-Backup\build_reports" "build_reports\" /e /i

REM Copy root files
copy "Shakshuka-v2.0.0-Clean-Backup\main.py" "."
copy "Shakshuka-v2.0.0-Clean-Backup\Shakshuka.exe" "."
copy "Shakshuka-v2.0.0-Clean-Backup\Shakshuka-Setup-v2.0.0-b3.exe" "."
copy "Shakshuka-v2.0.0-Clean-Backup\.gitignore" "."
copy "Shakshuka-v2.0.0-Clean-Backup\APPLICATION_QUICK_OVERVIEW.md" "."
copy "Shakshuka-v2.0.0-Clean-Backup\ICON_QUICK_REFERENCE.md" "."

echo.
echo ================================================
echo RESTORATION COMPLETE!
echo ================================================
echo.
echo The clean backup version has been restored.
echo Your previous state is backed up in: CURRENT_STATE_BACKUP
echo.
echo Files restored:
echo - Shakshuka.exe (latest executable)
echo - Shakshuka-Setup-v2.0.0-b3.exe (latest installer)
echo - Complete source code
echo - All assets and configuration
echo - Documentation and build reports
echo.
echo You can now run: python main.py --test
echo.
pause




