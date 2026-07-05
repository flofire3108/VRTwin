@echo off
REM VRTwin one-click launcher for Windows 10/11.
REM Creates a virtual environment on first run, installs dependencies, starts the avatar.
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
    echo Python was not found. Install Python 3.10-3.12 from https://www.python.org/downloads/
    echo IMPORTANT: tick "Add python.exe to PATH" during installation.
    pause
    exit /b 1
)

if not exist .venv (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

if not exist .venv\.deps_installed (
    echo Installing dependencies ^(first run only, this can take a few minutes^)...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo Dependency installation failed. See the error above.
        pause
        exit /b 1
    )
    echo ok > .venv\.deps_installed
)

if not exist .env (
    echo No .env file found. Copy .env.example to .env and fill in your API keys.
    pause
    exit /b 1
)

python main.py %*
pause
