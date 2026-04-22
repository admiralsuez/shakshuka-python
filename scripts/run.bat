@echo off
title Shakshuka - Modern Task Manager
echo.
echo ========================================
echo    Shakshuka - Modern Task Manager
echo ========================================
echo.
echo Starting Shakshuka...
echo.
echo The application will open in your default browser.
echo If it doesn't open automatically, go to: http://127.0.0.1:8989
echo.
echo Press Ctrl+C to stop the application.
echo.
REM Change directory to the project root (parent of this script)
cd /d "%~dp0.."

python main.py

pause
