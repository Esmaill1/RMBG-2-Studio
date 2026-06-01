@echo off
chcp 65001 >nul 2>&1
title RMBG-2-Studio

:: Check if virtual environment exists
if not exist "%~dp0venv\Scripts\activate.bat" (
    echo.
    echo ERROR: Virtual environment not found.
    echo Please run setup.bat first!
    echo.
    pause
    exit /b 1
)

:: Activate virtual environment
call "%~dp0venv\Scripts\activate.bat"

:: Navigate to app directory
cd /d "%~dp0app"

echo.
echo Starting RMBG-2-Studio...
echo The browser will open automatically when ready.
echo.
echo Press Ctrl+C to stop the server.
echo.

python flask_app.py

echo.
echo Server stopped. Press any key to exit.
pause