@echo off
echo ============================================
echo   RMBG-2-Studio - Starting Application
echo ============================================
echo.

cd /d "%~dp0app"

if not exist "env\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found!
    echo Please run setup.bat first.
    pause
    exit /b 1
)

echo Activating virtual environment...
call env\Scripts\activate.bat

echo Starting Gradio application...
echo.
echo The application will open in your browser automatically.
echo Press Ctrl+C to stop the server.
echo.
python app.py
