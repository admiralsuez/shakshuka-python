@echo off
title Shakshuka Installer Builder
echo Building Shakshuka Installer...
echo.

REM Check if Inno Setup is installed
if not exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    echo ERROR: Inno Setup 6 not found at C:\Program Files (x86)\Inno Setup 6\
    echo Please install Inno Setup 6 first.
    pause
    exit /b 1
)

REM Check if executable exists
if not exist "..\Shakshuka.exe" (
    echo ERROR: Shakshuka.exe not found in parent directory
    echo Please build the executable first using build.bat
    pause
    exit /b 1
)

REM Build the installer
echo Compiling installer...
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss

if %ERRORLEVEL% EQU 0 (
    echo.
    echo SUCCESS: Installer created successfully!
    echo Location: dist\Shakshuka-Setup-v1.0.0.exe
    echo.
    echo You can now distribute this installer to install Shakshuka on other computers.
) else (
    echo.
    echo ERROR: Installer compilation failed!
    echo Check the error messages above for details.
)

echo.
pause
