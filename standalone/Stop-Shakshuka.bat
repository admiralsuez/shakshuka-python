@echo off
title Shakshuka Server Manager
echo Stopping Shakshuka...
echo.

tasklist /FI "IMAGENAME eq Shakshuka.exe" 2>NUL | find /I /N "Shakshuka.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo Found running Shakshuka processes
    taskkill /F /IM Shakshuka.exe
    echo Shakshuka stopped successfully!
) else (
    echo No Shakshuka processes found
)

echo.
pause
