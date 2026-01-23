#!/bin/bash

echo "============================================"
echo "  RMBG-2-Studio - Starting Application"
echo "============================================"
echo

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/app"

if [ ! -f "env/bin/activate" ]; then
    echo "[ERROR] Virtual environment not found!"
    echo "Please run setup.sh first."
    exit 1
fi

echo "Activating virtual environment..."
source env/bin/activate

echo "Starting Gradio application..."
echo
echo "The application will open in your browser automatically."
echo "Press Ctrl+C to stop the server."
echo

# Enable MPS fallback for Apple Silicon
export PYTORCH_ENABLE_MPS_FALLBACK=1

python app.py
