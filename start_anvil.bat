@echo off
rem One-command launcher for the Anvil workbench (double-click me).
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo [anvil] ERROR: Python not found on PATH.
    echo Install Python 3.10+ from https://www.python.org/downloads/
    echo and check "Add python.exe to PATH" during setup.
    pause
    exit /b 1
)

python start_anvil.py %*
if errorlevel 1 (
    echo.
    echo [anvil] start_anvil.py exited with an error. See messages above.
    pause
    exit /b 1
)
endlocal
