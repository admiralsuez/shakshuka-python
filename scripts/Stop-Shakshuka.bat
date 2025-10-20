@echo off
title Shakshuka Server Manager
echo Stopping Shakshuka...
echo.

REM Kill Shakshuka.exe if running
tasklist /FI "IMAGENAME eq Shakshuka.exe" 2>NUL | find /I /N "Shakshuka.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo Found running Shakshuka.exe processes
    taskkill /F /IM Shakshuka.exe
    echo Shakshuka.exe stopped successfully!
)

REM Kill Python processes running main.py from Shakshuka directory
for /f "tokens=2" %%i in ('tasklist /FI "IMAGENAME eq python.exe" /FO CSV ^| findstr /I "python.exe"') do (
    wmic process where "ProcessId=%%i" get CommandLine /format:list 2>NUL | findstr /I "main.py" | findstr /I "shakshuka-python-beta" >NUL
    if not errorlevel 1 (
        echo Found Python process running Shakshuka main.py
        taskkill /F /PID %%i
        echo Python process stopped successfully!
    )
)

echo.
pause
