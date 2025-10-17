@echo off
title Shakshuka Data Directory Test
color 0A
echo.
echo ========================================
echo    SHAKSHUKA DATA DIRECTORY TEST
echo ========================================
echo.

echo This script tests Shakshuka's ability to handle
echo data directory creation issues on different systems.
echo.

REM Check if Shakshuka.exe exists
if not exist "Shakshuka.exe" (
    echo ERROR: Shakshuka.exe not found!
    echo Please ensure Shakshuka.exe is in the current directory.
    pause
    exit /b 1
)

echo Testing data directory creation...
echo.

REM Try to create a read-only directory to simulate permission issues
echo Creating test scenario...
mkdir test-readonly 2>nul
attrib +r test-readonly 2>nul

echo Starting Shakshuka.exe...
echo Check the console output for detailed error messages.
echo If the fix works, it should try multiple data directory locations.
echo.

start /wait "Shakshuka Test" "Shakshuka.exe"

echo.
echo Test completed!
echo.

REM Clean up test directory
rmdir /s /q test-readonly 2>nul

echo If you saw detailed error messages about data directory creation,
echo the improved error handling is working correctly.
echo.
pause



