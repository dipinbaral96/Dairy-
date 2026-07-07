@echo off
setlocal
cd /d "%~dp0"

REM =============================================================
REM Dairy Management System Windows Launcher
REM It detects Python, creates a fresh virtual environment,
REM installs requirements, prepares database, and starts server.
REM =============================================================

set "PY_CMD="

py -3 --version >nul 2>&1
if not errorlevel 1 set "PY_CMD=py -3"

if not defined PY_CMD (
    python --version >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python"
)

if not defined PY_CMD (
    python3 --version >nul 2>&1
    if not errorlevel 1 set "PY_CMD=python3"
)

if not defined PY_CMD (
    echo.
    echo ============================================================
    echo  ERROR: Python was not found on this computer.
    echo ============================================================
    echo.
    echo  Please install Python 3.11 or newer first.
    echo.
    echo  Recommended fix:
    echo  1. Download Python from: https://www.python.org/downloads/windows/
    echo  2. Run the installer.
    echo  3. Tick/check: Add python.exe to PATH
    echo  4. Click Install Now.
    echo  5. Close this window and double-click run_windows.bat again.
    echo.
    echo  If Python is already installed but still not detected:
    echo  Settings ^> Apps ^> Advanced app settings ^> App execution aliases
    echo  Turn OFF python.exe and python3.exe aliases.
    echo.
    pause
    exit /b 1
)

echo Using Python command: %PY_CMD%

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" --version >nul 2>&1
    if errorlevel 1 (
        echo Existing virtual environment is broken. Recreating it...
        rmdir /s /q ".venv"
    )
)

if not exist ".venv\Scripts\python.exe" (
    echo Creating virtual environment...
    %PY_CMD% -m venv .venv
    if errorlevel 1 (
        echo.
        echo Failed to create virtual environment.
        echo Please confirm Python is installed correctly and added to PATH.
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo Failed to activate virtual environment.
    pause
    exit /b 1
)

echo Installing requirements...
python -m ensurepip --upgrade >nul 2>&1
python -m pip install --upgrade pip
if errorlevel 1 (
    echo Failed to upgrade pip.
    pause
    exit /b 1
)

python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Failed to install project requirements. Please check your internet connection.
    pause
    exit /b 1
)

echo Preparing database...
python manage.py makemigrations
if errorlevel 1 (
    echo Failed during makemigrations.
    pause
    exit /b 1
)

python manage.py migrate
if errorlevel 1 (
    echo Failed during migrate.
    pause
    exit /b 1
)

python manage.py seed_demo
if errorlevel 1 (
    echo Demo data may already exist or seeding failed. Continuing...
)

echo.
echo ============================================================
echo  Dairy Management System is starting...
echo  Open: http://127.0.0.1:8000/
echo  Default admin: admin / Admin@12345
echo ============================================================
echo.
start "" "http://127.0.0.1:8000/"
python manage.py runserver 0.0.0.0:8000
pause
