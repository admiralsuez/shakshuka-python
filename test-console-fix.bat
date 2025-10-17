@echo off
title Shakshuka Console Test
color 0A
echo.
echo ========================================
echo    SHAKSHUKA CONSOLE TEST
echo ========================================
echo.

echo Testing Shakshuka.exe console output...
echo.

REM Check if Shakshuka.exe exists
if not exist "Shakshuka.exe" (
    echo ERROR: Shakshuka.exe not found!
    echo Please ensure Shakshuka.exe is in the current directory.
    pause
    exit /b 1
)

echo Starting Shakshuka.exe...
echo This will test if the console encoding issue is fixed.
echo.

REM Start Shakshuka.exe and capture output
start /wait "Shakshuka Test" "Shakshuka.exe"

echo.
echo Test completed!
echo If you saw the server start without encoding errors, the fix worked!
echo.
pause



