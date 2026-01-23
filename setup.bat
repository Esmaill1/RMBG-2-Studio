@echo off
setlocal enabledelayedexpansion

echo ============================================
echo   RMBG-2-Studio Standalone Setup (Windows)
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH
    echo Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

echo [1/4] Creating virtual environment...
cd /d "%~dp0app"
if not exist "env" (
    python -m venv env
    echo       Virtual environment created in app\env
) else (
    echo       Virtual environment already exists
)

echo.
echo [2/4] Activating virtual environment...
call env\Scripts\activate.bat

echo.
echo [3/4] Installing PyTorch with CUDA 12.4 support...
echo       (This may take several minutes on first run)
pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124

echo.
echo [4/4] Installing other dependencies...
pip install -r requirements.txt
pip install pydantic==2.10.6

echo.
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo To run the application, use: run.bat
echo.
pause
