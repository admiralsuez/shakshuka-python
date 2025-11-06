@echo off
REM Silent launcher for Shakshuka - runs in background without console window

REM Try to find Shakshuka.exe (current directory first for latest build)
if exist "Shakshuka.exe" (
    set "SHAKSHUKA_PATH=Shakshuka.exe"
) else if exist "%PROGRAMFILES%\Shakshuka\Shakshuka.exe" (
    set "SHAKSHUKA_PATH=%PROGRAMFILES%\Shakshuka\Shakshuka.exe"
) else if exist "%USERPROFILE%\Desktop\Shakshuka.exe" (
    set "SHAKSHUKA_PATH=%USERPROFILE%\Desktop\Shakshuka.exe"
) else (
    REM If not found, try to run VBS silent launcher
    if exist "Start-Shakshuka-Silent.vbs" (
        cscript //nologo "Start-Shakshuka-Silent.vbs"
        exit /b 0
    ) else (
        exit /b 1
    )
)

REM Start Shakshuka silently in background
start /B "" "%SHAKSHUKA_PATH%" >nul 2>&1
