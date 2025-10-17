@echo off
title Shakshuka Server Manager
echo Starting Shakshuka...
echo.

REM Try to find Shakshuka.exe
if exist "%USERPROFILE%\Desktop\Shakshuka.exe" (
    set "SHAKSHUKA_PATH=%USERPROFILE%\Desktop\Shakshuka.exe"
) else if exist "%PROGRAMFILES%\Shakshuka\Shakshuka.exe" (
    set "SHAKSHUKA_PATH=%PROGRAMFILES%\Shakshuka\Shakshuka.exe"
) else if exist "Shakshuka.exe" (
    set "SHAKSHUKA_PATH=Shakshuka.exe"
) else (
    echo ERROR: Could not find Shakshuka.exe
    echo Please ensure Shakshuka is installed
    pause
    exit /b 1
)

echo Found Shakshuka at: %SHAKSHUKA_PATH%
echo Starting server...
echo.
echo The application will open in your browser at http://127.0.0.1:8989
echo Press Ctrl+C to stop the server
echo.

start "" "%SHAKSHUKA_PATH%"
