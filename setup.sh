#!/bin/bash

echo "============================================"
echo "  RMBG-2-Studio Standalone Setup"
echo "============================================"
echo

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/app"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python3 is not installed"
    echo "Please install Python 3.10+ first"
    exit 1
fi

echo "[1/4] Creating virtual environment..."
if [ ! -d "env" ]; then
    python3 -m venv env
    echo "       Virtual environment created in app/env"
else
    echo "       Virtual environment already exists"
fi

echo
echo "[2/4] Activating virtual environment..."
source env/bin/activate

echo
echo "[3/4] Installing PyTorch..."
echo "       Detecting GPU type..."

# Detect GPU and install appropriate PyTorch version
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    if [[ $(uname -m) == "arm64" ]]; then
        echo "       Detected: Apple Silicon (MPS)"
        pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0
    else
        echo "       Detected: Intel Mac"
        pip install torch==2.1.2 torchvision==0.16.2 torchaudio==2.1.2
    fi
elif command -v nvidia-smi &> /dev/null; then
    echo "       Detected: NVIDIA GPU"
    pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cu124
elif [ -d "/opt/rocm" ]; then
    echo "       Detected: AMD GPU (ROCm)"
    pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/rocm6.2.4
else
    echo "       Detected: CPU only"
    pip install torch==2.6.0 torchvision==0.21.0 torchaudio==2.6.0 --index-url https://download.pytorch.org/whl/cpu
fi

echo
echo "[4/4] Installing other dependencies..."
pip install -r requirements.txt
pip install pydantic==2.10.6

echo
echo "============================================"
echo "  Setup Complete!"
echo "============================================"
echo
echo "To run the application, use: ./run.sh"
echo
