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

:: Step 2: Check Visual C++ Redistributable
echo [Step 2] Checking Visual C++ Redistributable...
set VC_INSTALLED=0
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Installed >nul 2>&1
if not errorlevel 1 set VC_INSTALLED=1
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Installed >nul 2>&1
if not errorlevel 1 set VC_INSTALLED=1

if "%VC_INSTALLED%"=="1" (
    echo Visual C++ Redistributable already installed, skipping...
) else (
    echo Visual C++ Redistributable not found. Downloading and installing...
    powershell -Command "Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile '%TEMP%\vc_redist.x64.exe'"
    if errorlevel 1 (
        echo.
        echo ERROR: Could not download Visual C++ Redistributable.
        echo Please download and install it manually from:
        echo https://aka.ms/vs/17/release/vc_redist.x64.exe
        echo Then run setup.bat again.
        echo.
        pause
        exit /b 1
    )
    echo Installing Visual C++ Redistributable...
    "%TEMP%\vc_redist.x64.exe" /install /quiet /norestart
    if %ERRORLEVEL% EQU 3010 (
        echo Visual C++ Redistributable installed (reboot recommended).
    ) else if %ERRORLEVEL% NEQ 0 (
        del "%TEMP%\vc_redist.x64.exe" >nul 2>&1
        echo.
        echo ERROR: Visual C++ Redistributable installation failed (exit code: %ERRORLEVEL%).
        echo This may require administrator privileges.
        echo Please try one of these options:
        echo   1. Right-click setup.bat and select "Run as administrator"
        echo   2. Download and install it manually from:
        echo      https://aka.ms/vs/17/release/vc_redist.x64.exe
        echo Then run setup.bat again.
        echo.
        pause
        exit /b 1
    ) else (
        echo Visual C++ Redistributable installed successfully.
    )
    del "%TEMP%\vc_redist.x64.exe" >nul 2>&1
)
echo.

:: Step 3: Create virtual environment
echo [Step 3] Creating virtual environment...
if exist "%~dp0venv\Scripts\activate.bat" (
    call "%~dp0venv\Scripts\activate.bat"
    python -c "import torch" >nul 2>&1
    if errorlevel 1 (
        echo Existing virtual environment has a broken PyTorch installation.
        echo Recreating virtual environment...
        call deactivate >nul 2>&1
        rmdir /s /q "%~dp0venv"
        python -m venv "%~dp0venv"
        if errorlevel 1 (
            echo.
            echo ERROR: Failed to create virtual environment.
            echo.
            pause
            exit /b 1
        )
        echo Virtual environment recreated.
    ) else (
        echo Virtual environment already exists and is healthy, skipping...
        call deactivate >nul 2>&1
    )
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

:: Step 4: Activate virtual environment
echo [Step 4] Activating virtual environment...
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

:: Step 5: Install CPU-only PyTorch
echo [Step 5] Installing PyTorch (CPU-only for minimal resource usage)...
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 (
    echo.
    echo ERROR: Failed to install PyTorch.
    echo Check your internet connection and try again.
    echo If you see DLL errors later, make sure Visual C++ Redistributable is installed.
    echo Download from: https://aka.ms/vs/17/release/vc_redist.x64.exe
    echo.
    pause
    exit /b 1
)
echo PyTorch installed.
echo.

:: Step 6: Install application dependencies
echo [Step 6] Installing application dependencies...
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

:: Step 7: Pre-download the model
echo [Step 7] Pre-downloading the AI model (this may take a few minutes)...
python -c "from transformers import AutoModelForImageSegmentation; print('Downloading model...'); AutoModelForImageSegmentation.from_pretrained('cocktailpeanut/rm', trust_remote_code=True); print('Model downloaded and cached!')"
if errorlevel 1 (
    echo.
    echo WARNING: Model download was skipped. It will be downloaded automatically on first run (this may take a few minutes).
    echo.
) else (
    echo Model downloaded and cached.
)
echo.

:: Success
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