#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

error() { echo -e "${RED}[ERROR]${NC} $1" >&2; exit 1; }
info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }

echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}  RMBG-2-Studio Setup${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""
echo "Choose installation mode:"
echo -e "  ${YELLOW}1)${NC} CPU-only  (smaller download, no GPU required)"
echo -e "  ${YELLOW}2)${NC} GPU/CUDA  (requires NVIDIA GPU + drivers)"
echo ""
read -p "Enter choice [1/2]: " MODE

if [ "$MODE" != "1" ] && [ "$MODE" != "2" ]; then
    error "Invalid choice '$MODE'. Must be 1 or 2."
fi

command -v python3 >/dev/null 2>&1 || error "python3 is not installed. Please install Python 3.8+ first."

PYTHON_VER=$(python3 -c "import sys; print(sys.version_info[:2])")
PYTHON_MAJOR=$(echo "$PYTHON_VER" | cut -d' ' -f1 | tr -d ',')
PYTHON_MINOR=$(echo "$PYTHON_VER" | cut -d' ' -f2 | tr -d ',')

if [ "$PYTHON_MAJOR" -lt 3 ] || [ "$PYTHON_MINOR" -lt 8 ]; then
    error "Python 3.8+ required (found $PYTHON_MAJOR.$PYTHON_MINOR)."
fi
ok "Python $PYTHON_MAJOR.$PYTHON_MINOR detected"

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_ROOT/venv"

info "Creating virtual environment at $VENV_DIR..."
python3 -m venv "$VENV_DIR" || error "Failed to create virtual environment."

source "$VENV_DIR/bin/activate" || error "Failed to activate virtual environment."
ok "Virtual environment activated"

info "Upgrading pip..."
pip install --upgrade pip --quiet || error "Failed to upgrade pip."

if [ "$MODE" = "1" ]; then
    echo ""
    info "Installing CPU-only PyTorch..."
    pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu || error "Failed to install PyTorch (CPU)."
    ok "PyTorch (CPU) installed"

    info "Installing CPU requirements..."
    pip install -r "$PROJECT_ROOT/app/requirements.txt" || error "Failed to install requirements.txt."
    ok "CPU requirements installed"

    echo ""
    info "Verifying installation..."
    python3 -c "import torch; print(f'  PyTorch {torch.__version__} (CPU)')" || error "PyTorch verification failed."
    ok "CPU installation verified"

elif [ "$MODE" = "2" ]; then
    echo ""
    info "Installing GPU (CUDA) PyTorch..."
    pip install torch torchvision || error "Failed to install PyTorch (CUDA)."
    ok "PyTorch (CUDA) installed"

    info "Installing GPU requirements..."
    pip install -r "$PROJECT_ROOT/app/requirements-gpu.txt" || error "Failed to install requirements-gpu.txt."
    ok "GPU requirements installed"

    echo ""
    info "Verifying installation..."
    python3 -c "
import torch
print(f'  PyTorch  : {torch.__version__}')
print(f'  CUDA     : {torch.version.cuda}')
avail = torch.cuda.is_available()
print(f'  GPU avail: {avail}')
if avail:
    print(f'  GPU name : {torch.cuda.get_device_name(0)}')
else:
    print('  WARNING: CUDA not available — check driver/NVIDIA setup')
" || error "PyTorch verification failed."
    ok "GPU installation verified"
fi

echo ""
MODEL_DIR="$PROJECT_ROOT/model"

if [ -f "$MODEL_DIR/config.json" ]; then
    ok "Model already saved locally — no download needed."
else
    info "Pre-downloading AI model and saving locally..."
    python3 -c "
import os
from transformers import AutoModelForImageSegmentation
model_dir = '$MODEL_DIR'
os.makedirs(model_dir, exist_ok=True)
print('Downloading model...')
model = AutoModelForImageSegmentation.from_pretrained('cocktailpeanut/rm', trust_remote_code=True)
model.save_pretrained(model_dir)
print('Model saved to local cache!')
" || echo -e "${YELLOW}[WARN]${NC} Model download skipped. It will be downloaded on first run."
    ok "Model saved locally. No internet needed on future runs."
fi

echo ""
echo -e "${BOLD}${GREEN}========================================${NC}"
echo -e "${BOLD}${GREEN}  Setup Complete!${NC}"
echo -e "${BOLD}${GREEN}========================================${NC}"
echo ""
echo -e "To run the app:"
echo -e "  ${CYAN}source venv/bin/activate${NC}"
if [ "$MODE" = "1" ]; then
    echo -e "  ${CYAN}python app/flask_app.py${NC}"
else
    echo -e "  ${CYAN}python app/flask_app_gpu.py${NC}"
fi
echo ""