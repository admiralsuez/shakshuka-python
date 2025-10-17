@echo off
title Shakshuka Portable
echo Starting Shakshuka Portable...
echo.

REM Check if Shakshuka.exe exists
if not exist "Shakshuka.exe" (
    echo ERROR: Shakshuka.exe not found!
    echo Please ensure all files are extracted properly.
    pause
    exit /b 1
)

echo Starting server...
echo The application will open in your browser at http://127.0.0.1:8989
echo Press Ctrl+C to stop the server
echo.

start "" "Shakshuka.exe"
