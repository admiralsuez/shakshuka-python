@echo off
REM Shakshuka Autostart Script
REM This script is designed to be used for Windows autostart

REM Get the directory where this script is located
set "SCRIPT_DIR=%~dp0"

REM Try to find Shakshuka.exe (prioritize current directory for latest build)
if exist "%SCRIPT_DIR%Shakshuka.exe" (
    set "SHAKSHUKA_PATH=%SCRIPT_DIR%Shakshuka.exe"
) else if exist "%PROGRAMFILES%\Shakshuka\Shakshuka.exe" (
    set "SHAKSHUKA_PATH=%PROGRAMFILES%\Shakshuka\Shakshuka.exe"
) else if exist "%USERPROFILE%\Desktop\Shakshuka.exe" (
    set "SHAKSHUKA_PATH=%USERPROFILE%\Desktop\Shakshuka.exe"
) else (
    REM If not found, exit silently
    exit /b 1
)

REM Start Shakshuka silently (no console window)
start "" "%SHAKSHUKA_PATH%"

REM Exit successfully
exit /b 0
