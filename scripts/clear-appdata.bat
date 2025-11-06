@echo off
:: Clear Shakshuka AppData for Fresh PIN Setup
:: This removes old authentication data to force PIN setup screen

title Shakshuka - Clear AppData
color 0E

echo.
echo ====================================
echo   Shakshuka AppData Cleaner
echo ====================================
echo.
echo This will delete old Shakshuka data from AppData
echo allowing you to test the PIN setup screen.
echo.
echo WARNING: This will delete:
echo  - Old login data
echo  - Saved tasks
echo  - Settings
echo  - All user data
echo.

set /p "confirm=Are you sure you want to continue? (Y/N): "
if /i not "%confirm%"=="Y" (
    echo.
    echo Operation cancelled.
    timeout /t 3
    exit /b 0
)

echo.
echo Clearing AppData...

:: Stop Shakshuka if running
tasklist /FI "IMAGENAME eq Shakshuka.exe" 2>NUL | find /I /N "Shakshuka.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo Stopping Shakshuka...
    taskkill /F /IM Shakshuka.exe >NUL 2>&1
    timeout /t 2 >NUL
)

:: Clear AppData
set "APPDATA_DIR=%APPDATA%\Shakshuka"
if exist "%APPDATA_DIR%" (
    echo Deleting: %APPDATA_DIR%
    rd /s /q "%APPDATA_DIR%" >NUL 2>&1
    if exist "%APPDATA_DIR%" (
        echo ERROR: Failed to delete AppData directory
        echo Please close all Shakshuka windows and try again
        pause
        exit /b 1
    ) else (
        echo SUCCESS: AppData cleared
    )
) else (
    echo No AppData found - already clean
)

:: Clear temp data
set "LOCAL_DIR=%LOCALAPPDATA%\Shakshuka"
if exist "%LOCAL_DIR%" (
    echo Deleting: %LOCAL_DIR%
    rd /s /q "%LOCAL_DIR%" >NUL 2>&1
)

echo.
echo ====================================
echo   Cleanup Complete!
echo ====================================
echo.
echo Next time you launch Shakshuka:
echo  - PIN setup screen will appear
echo  - You'll create a new 4-digit PIN
echo  - All data will be fresh
echo.
pause





