@echo off
setlocal
chcp 65001 >nul 2>&1
title RMBG-2-Studio Setup

echo ================================================
echo   RMBG-2-Studio Setup
echo ================================================
echo:

:: Step 1: Check Python
echo [Step 1] Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 goto :python_missing

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYTHON_VER=%%v
echo Found Python %PYTHON_VER%

python -c "import sys; exit(0 if sys.version_info >= (3,8) else 1)" >nul 2>&1
if errorlevel 1 goto :python_old

echo Python check passed.
echo:

:: Step 2: Check Visual C++ Redistributable
echo [Step 2] Checking Visual C++ Redistributable...
reg query "HKLM\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Installed >nul 2>&1
if not errorlevel 1 goto :vc_done
reg query "HKLM\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64" /v Installed >nul 2>&1
if not errorlevel 1 goto :vc_done

echo Visual C++ Redistributable not found. Downloading...
powershell -Command "Invoke-WebRequest -Uri 'https://aka.ms/vs/17/release/vc_redist.x64.exe' -OutFile '%TEMP%\vc_redist.x64.exe'"
if errorlevel 1 goto :vc_download_fail

echo Installing Visual C++ Redistributable...
"%TEMP%\vc_redist.x64.exe" /install /quiet /norestart
if errorlevel 3010 goto :vc_installed_reboot
if errorlevel 1 goto :vc_install_fail

echo Visual C++ Redistributable installed successfully.
del "%TEMP%\vc_redist.x64.exe" >nul 2>&1
goto :vc_done

:vc_installed_reboot
echo Visual C++ Redistributable installed (reboot recommended).
del "%TEMP%\vc_redist.x64.exe" >nul 2>&1
goto :vc_done

:vc_download_fail
echo:
echo ERROR: Could not download Visual C++ Redistributable.
echo Please download and install it manually from:
echo https://aka.ms/vs/17/release/vc_redist.x64.exe
echo Then run setup.bat again.
echo:
goto :end

:vc_install_fail
del "%TEMP%\vc_redist.x64.exe" >nul 2>&1
echo:
echo ERROR: Visual C++ Redistributable installation failed.
echo This may require administrator privileges.
echo Please try one of these options:
echo   1. Right-click setup.bat and select "Run as administrator"
echo   2. Download and install it manually from:
echo      https://aka.ms/vs/17/release/vc_redist.x64.exe
echo Then run setup.bat again.
echo:
goto :end

:vc_done
echo:

:: Step 3: Create virtual environment
echo [Step 3] Setting up virtual environment...
if not exist "%~dp0venv\Scripts\activate.bat" (
    echo Creating new virtual environment...
    python -m venv "%~dp0venv"
    if errorlevel 1 goto :venv_fail
    echo Virtual environment created.
    goto :venv_done
)

:: venv exists — check if PyTorch works
call "%~dp0venv\Scripts\activate.bat"
python -c "import torch" >nul 2>&1
if not errorlevel 1 (
    echo Virtual environment already exists and is healthy, skipping...
    call deactivate >nul 2>&1
    goto :venv_done
)

:: torch broken — recreate venv
echo Existing virtual environment has a broken PyTorch installation.
echo Recreating virtual environment...
call deactivate >nul 2>&1
rmdir /s /q "%~dp0venv"
python -m venv "%~dp0venv"
if errorlevel 1 goto :venv_fail
echo Virtual environment recreated.
goto :venv_done

:venv_fail
echo:
echo ERROR: Failed to create virtual environment.
echo:
goto :end

:venv_done
echo:

:: Step 4: Activate virtual environment
echo [Step 4] Activating virtual environment...
call "%~dp0venv\Scripts\activate.bat"
if errorlevel 1 goto :venv_activate_fail
echo Virtual environment activated.
echo:
goto :step5

:venv_activate_fail
echo:
echo ERROR: Failed to activate virtual environment.
echo:
goto :end

:: Step 5: Install PyTorch (auto-detect CUDA)
:step5
echo [Step 5] Detecting GPU and installing PyTorch...
nvidia-smi >nul 2>&1
if not errorlevel 1 goto :install_cuda

echo No NVIDIA GPU detected. Installing PyTorch (CPU-only)...
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto :pytorch_fail_cpu
set "GPU_MODE=cpu"
echo PyTorch installed (CPU-only).
goto :step5_done

:install_cuda
echo NVIDIA GPU detected. Installing PyTorch with CUDA support...
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
if errorlevel 1 goto :pytorch_fail_cuda
set "GPU_MODE=cuda"
echo PyTorch installed with CUDA support.
goto :step5_done

:pytorch_fail_cuda
echo:
echo ERROR: Failed to install PyTorch with CUDA support.
echo Check your internet connection and try again.
echo:
goto :end

:pytorch_fail_cpu
echo:
echo ERROR: Failed to install PyTorch.
echo Check your internet connection and try again.
echo If you see DLL errors later, make sure Visual C++ Redistributable is installed.
echo Download from: https://aka.ms/vs/17/release/vc_redist.x64.exe
echo:
goto :end

:step5_done
echo:

:: Step 6: Install application dependencies
echo [Step 6] Installing application dependencies...
pip install -r "%~dp0app\requirements.txt"
if errorlevel 1 goto :deps_fail
echo Dependencies installed.
echo:
goto :step7

:deps_fail
echo:
echo ERROR: Failed to install dependencies.
echo Check your internet connection and try again.
echo:
goto :end

:: Step 7: Pre-download the model
:step7
echo [Step 7] Pre-downloading the AI model (this may take a few minutes)...
python -c "import os, sys; from transformers import AutoModelForImageSegmentation; model_dir = os.path.join(sys.argv[1], 'model'); os.makedirs(model_dir, exist_ok=True); print('Downloading model...'); model = AutoModelForImageSegmentation.from_pretrained('cocktailpeanut/rm', trust_remote_code=True); model.save_pretrained(model_dir); print('Model downloaded and cached locally!')" "%~dp0."
if errorlevel 1 goto :model_fail
echo Model downloaded and cached.
echo:
goto :step8

:model_fail
echo:
echo WARNING: Model download was skipped. It will be downloaded automatically on first run (this may take a few minutes).
echo:
goto :step8

:: Step 8: Verify installation
:step8
echo [Step 8] Verifying installation...
python -c "import torch; cuda=torch.cuda.is_available(); print(f'PyTorch {torch.__version__}'); print(f'CUDA available: {cuda}'); print(f'GPU: {torch.cuda.get_device_name(0)}' if cuda else 'Running in CPU mode')"
echo:

:: Success
echo ================================================
echo   Setup complete!
echo ================================================
echo:
if "%GPU_MODE%"=="cuda" (
    echo   Mode: GPU ^(CUDA^)
) else (
    echo   Mode: CPU
)
echo:
echo   You can now run the app by double-clicking
echo   run.bat
echo:
echo ================================================
echo:
goto :end

:: Error labels for Step 1
:python_missing
echo:
echo ERROR: Python is not installed or not in PATH.
echo Please download Python 3.8+ from:
echo https://www.python.org/downloads/
echo:
echo IMPORTANT: Check "Add Python to PATH" during installation.
echo:
goto :end

:python_old
echo:
echo ERROR: Python version must be 3.8 or higher.
echo Your version: %PYTHON_VER%
echo Please download a newer version from:
echo https://www.python.org/downloads/
echo:
goto :end

:end
pause
endlocal