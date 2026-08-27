@echo off
REM SMS Setup Script for Clinic System
REM This script installs the Africa's Talking SDK and checks configuration

echo ========================================
echo SMS Reminder Setup
echo ========================================
echo.

cd /d "%~dp0.."

echo [1/3] Checking Python virtual environment...
if not exist ".venv\Scripts\python.exe" (
    echo ERROR: Virtual environment not found. Please run: python -m venv .venv
    pause
    exit /b 1
)
echo Virtual environment found.
echo.

echo [2/3] Installing Africa's Talking SDK...
.venv\Scripts\pip.exe install africastalking
if errorlevel 1 (
    echo ERROR: Failed to install africastalking package
    pause
    exit /b 1
)
echo Africa's Talking SDK installed successfully.
echo.

echo [3/3] Checking configuration...
findstr /C:"AT_API_KEY=" ".env" >nul
if errorlevel 1 (
    echo WARNING: AT_API_KEY not found in .env file
    echo.
    echo Please edit .env and add your Africa's Talking credentials:
    echo   AT_API_KEY=your_api_key_here
    echo   AT_USERNAME=your_username_here
    echo.
    echo Get credentials from: https://africastalking.com
) else (
    echo Configuration found in .env file
    echo SMS reminders are ready to use!
)
echo.

echo ========================================
echo Setup Complete!
echo ========================================
echo.
echo Next steps:
echo 1. Get API credentials from https://africastalking.com
echo 2. Edit .env file and add AT_API_KEY and AT_USERNAME
echo 3. Restart the server
echo 4. Test with: python manage.py send_reminders --dry-run
echo.
pause
