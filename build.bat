@echo off
title Shakshuka Builder
echo.
echo ========================================
echo    Shakshuka - Build Executable
echo ========================================
echo.
echo This will build Shakshuka as a standalone executable.
echo.
echo Press any key to continue or Ctrl+C to cancel...
pause >nul
echo.
echo Building executable...
echo.

python build.py

echo.
echo Build process completed!
echo.
pause

