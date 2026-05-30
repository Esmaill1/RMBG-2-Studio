@echo off
chcp 65001 >nul 2>&1
title RMBG-2-Studio Setup

echo ================================================
echo   RMBG-2-Studio Setup
echo ================================================
echo.

:: Step 1: Check Python
echo [Step 1] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python is not installed or not in PATH.
    echo Please download Python 3.8+ from:
    echo https://www.python.org/downloads/
    echo.
    echo IMPORTANT: Check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYTHON_VER=%%v
echo Found Python %PYTHON_VER%

:: Check version is 3.8+
python -c "import sys; exit(0 if sys.version_info >= (3,8) else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python version must be 3.8 or higher.
    echo Your version: %PYTHON_VER%
    echo Please download a newer version from:
    echo https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo Python check passed.
echo.

:: Step 2: Create virtual environment
echo [Step 2] Creating virtual environment...
if exist "%~dp0venv\Scripts\activate.bat" (
    echo Virtual environment already exists, skipping...
) else (
    python -m venv "%~dp0venv"
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to create virtual environment.
        echo Try running: python -m venv "%~dp0venv"
        echo.
        pause
        exit /b 1
    )
    echo Virtual environment created.
)
echo.

:: Step 3: Activate virtual environment
echo [Step 3] Activating virtual environment...
call "%~dp0venv\Scripts\activate.bat"
if errorlevel 1 (
    echo.
    echo ERROR: Failed to activate virtual environment.
    echo.
    pause
    exit /b 1
)
echo Virtual environment activated.
echo.

:: Step 4: Install CPU-only PyTorch
echo [Step 4] Installing PyTorch (CPU-only for minimal resource usage)...
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install PyTorch.
    echo Check your internet connection and try again.
    echo.
    pause
    exit /b 1
)
echo PyTorch installed.
echo.

:: Step 5: Install application dependencies
echo [Step 5] Installing application dependencies...
pip install -r "%~dp0app\requirements.txt"
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install dependencies.
    echo Check your internet connection and try again.
    echo.
    pause
    exit /b 1
)
echo Dependencies installed.
echo.

:: Step 6: Pre-download the model
echo [Step 6] Pre-downloading the AI model (this may take a few minutes)...
python -c "from transformers import AutoModelForImageSegmentation; print('Downloading model...'); AutoModelForImageSegmentation.from_pretrained('cocktailpeanut/rm', trust_remote_code=True); print('Model downloaded and cached!')"
if errorlevel 1 (
    echo.
    echo ERROR: Failed to download the model.
    echo Check your internet connection and try again.
    echo The model will also download automatically on first run.
    echo.
    pause
    exit /b 1
)
echo Model downloaded and cached.
echo.

:: Step 7: Success
echo ================================================
echo   Setup complete!
echo ================================================
echo.
echo   You can now run the app by double-clicking
echo   run.bat
echo.
echo ================================================
echo.

pause