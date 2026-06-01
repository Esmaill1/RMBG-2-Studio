@echo off
chcp 65001 >nul 2>&1
title RMBG-2-Studio Setup

set LOGFILE=%~dp0setup_log.txt
echo Setup started at %date% %time% > "%LOGFILE%"

echo ================================================
echo   RMBG-2-Studio Setup
echo ================================================
echo   Log file: %LOGFILE%
echo ================================================
echo.

:: Step 1: Check Python
echo [1/7] Checking Python installation...
echo [1/7] Checking Python... >> "%LOGFILE%"
python --version
python --version >> "%LOGFILE%" 2>&1
if errorlevel 1 goto :python_not_found

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYTHON_VER=%%v
echo       Found Python %PYTHON_VER%

python -c "import sys; exit(0 if sys.version_info >= (3,8) else 1)" >nul 2>&1
if errorlevel 1 goto :python_version_old

echo       Version check passed (3.8+ required)
echo [OK] Python %PYTHON_VER% >> "%LOGFILE%"
echo.

:: Step 2: Check Visual C++ Redistributable
echo [2/7] Checking Visual C++ Redistributable...
echo [2/7] Checking VC++ Redist... >> "%LOGFILE%"
set VC_INSTALLED=0
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Installed >nul 2>&1
if not errorlevel 1 set VC_INSTALLED=1
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Installed >nul 2>&1
if not errorlevel 1 set VC_INSTALLED=1

if "%VC_INSTALLED%"=="1" goto :vc_already_installed
goto :vc_need_install

:vc_already_installed
echo       Already installed, skipping
echo [OK] VC++ Redist already installed >> "%LOGFILE%"
echo.
goto :step3

:vc_need_install
echo       Not found. Downloading...
echo [INFO] VC++ Redist not found, downloading... >> "%LOGFILE%"
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Write-Host 'Downloading VC++ Redistributable...'; Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile '%TEMP%\vc_redist.x64.exe'; Write-Host 'Download complete.'"
if errorlevel 1 goto :vc_download_fail

echo       Installing...
"%TEMP%\vc_redist.x64.exe" /install /quiet /norestart
set VC_EXIT=%ERRORLEVEL%
del "%TEMP%\vc_redist.x64.exe" >nul 2>&1

if %VC_EXIT% EQU 3010 (
    echo       Installed successfully (reboot recommended)
    echo [OK] VC++ Redist installed (reboot needed) >> "%LOGFILE%"
    echo.
    goto :step3
)
if %VC_EXIT% NEQ 0 goto :vc_install_fail

echo       Installed successfully
echo [OK] VC++ Redist installed >> "%LOGFILE%"
echo.
goto :step3

:vc_download_fail
echo.
echo ERROR: Could not download Visual C++ Redistributable.
echo [FAIL] VC++ Redist download failed >> "%LOGFILE%"
echo Please download and install it manually from:
echo https://aka.ms/vs/17/release/vc_redist.x64.exe
echo Then run setup.bat again.
echo.
pause
exit /b 1

:vc_install_fail
echo.
echo ERROR: Visual C++ Redistributable installation failed (exit code: %VC_EXIT%).
echo [FAIL] VC++ Redist install failed: %VC_EXIT% >> "%LOGFILE%"
echo This may require administrator privileges.
echo Please try one of these options:
echo   1. Right-click setup.bat and select "Run as administrator"
echo   2. Download and install it manually from:
echo      https://aka.ms/vs/17/release/vc_redist.x64.exe
echo Then run setup.bat again.
echo.
pause
exit /b 1

:step3
:: Step 3: Create virtual environment
echo [3/7] Creating virtual environment...
echo [3/7] Creating venv... >> "%LOGFILE%"
if not exist "%~dp0venv\Scripts\activate.bat" goto :venv_create

call "%~dp0venv\Scripts\activate.bat"
python -c "import torch" >nul 2>&1
if not errorlevel 1 goto :venv_healthy

echo       Existing venv has broken PyTorch, recreating...
echo [INFO] Broken venv, recreating... >> "%LOGFILE%"
call deactivate >nul 2>&1
rmdir /s /q "%~dp0venv"
python -m venv "%~dp0venv"
if errorlevel 1 goto :venv_fail
echo       Virtual environment recreated
echo [OK] venv recreated >> "%LOGFILE%"
echo.
goto :step4

:venv_healthy
echo       Already exists and is healthy, skipping
echo [OK] venv exists and healthy >> "%LOGFILE%"
call deactivate >nul 2>&1
echo.
goto :step4

:venv_create
python -m venv "%~dp0venv"
if errorlevel 1 goto :venv_fail
echo       Virtual environment created
echo [OK] venv created >> "%LOGFILE%"
echo.
goto :step4

:venv_fail
echo.
echo ERROR: Failed to create virtual environment.
echo [FAIL] venv creation failed >> "%LOGFILE%"
echo.
pause
exit /b 1

:step4
:: Step 4: Activate virtual environment
echo [4/7] Activating virtual environment...
echo [4/7] Activating venv... >> "%LOGFILE%"
call "%~dp0venv\Scripts\activate.bat"
if errorlevel 1 goto :venv_activate_fail

echo       Activated successfully
echo [OK] venv activated >> "%LOGFILE%"
echo.
goto :step5

:venv_activate_fail
echo.
echo ERROR: Failed to activate virtual environment.
echo [FAIL] venv activation failed >> "%LOGFILE%"
echo.
pause
exit /b 1

:step5
:: Step 5: Install CPU-only PyTorch
echo [5/7] Installing PyTorch (CPU-only)...
echo       This may take a few minutes. Download progress shown below:
echo.
echo [5/7] Installing PyTorch... >> "%LOGFILE%"
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto :pytorch_fail

echo.
echo       PyTorch installed successfully
echo [OK] PyTorch installed >> "%LOGFILE%"
echo.
goto :step6

:pytorch_fail
echo.
echo ERROR: Failed to install PyTorch.
echo [FAIL] PyTorch install failed >> "%LOGFILE%"
echo Check your internet connection and try again.
echo.
pause
exit /b 1

:step6
:: Step 6: Install application dependencies
echo [6/7] Installing application dependencies...
echo       This may take a few minutes. Download progress shown below:
echo.
echo [6/7] Installing app deps... >> "%LOGFILE%"
pip install -r "%~dp0app\requirements.txt"
if errorlevel 1 goto :deps_fail

echo.
echo       Dependencies installed successfully
echo [OK] App deps installed >> "%LOGFILE%"
echo.
goto :step7

:deps_fail
echo.
echo ERROR: Failed to install dependencies.
echo [FAIL] App deps install failed >> "%LOGFILE%"
echo Check your internet connection and try again.
echo.
pause
exit /b 1

:step7
:: Step 7: Pre-download the AI model
echo [7/7] Pre-downloading the AI model...
echo       This may take a few minutes. Download progress shown below:
echo.
echo [7/7] Downloading model... >> "%LOGFILE%"
python "%~dp0download_model.py"
if not errorlevel 1 goto :model_ok
echo.
echo WARNING: Model download was skipped.
echo       It will be downloaded automatically on first run.
echo [WARN] Model download skipped >> "%LOGFILE%"
echo.
goto :done

:model_ok
echo.
echo       Model downloaded and cached successfully
echo       No internet needed on future runs!
echo [OK] Model cached >> "%LOGFILE%"
echo.

:done
echo ================================================
echo   Setup complete!
echo ================================================
echo   Log saved to: %LOGFILE%
echo ================================================
echo.
echo   You can now run the app by double-clicking
echo   run.bat
echo.

echo Setup completed at %date% %time% >> "%LOGFILE%"

pause

:python_not_found
echo.
echo ERROR: Python is not installed or not in PATH.
echo [FAIL] Python not found >> "%LOGFILE%"
echo Please download Python 3.8+ from:
echo https://www.python.org/downloads/
echo.
echo IMPORTANT: Check "Add Python to PATH" during installation.
echo.
pause
exit /b 1

:python_version_old
echo.
echo ERROR: Python version must be 3.8 or higher.
echo Your version: %PYTHON_VER%
echo [FAIL] Python version too old >> "%LOGFILE%"
echo Please download a newer version from:
echo https://www.python.org/downloads/
echo.
pause
exit /b 1
