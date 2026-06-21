#!/bin/bash
set -e

# Get project root directory
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

# Check if virtual environment exists
if [ ! -f "$PROJECT_ROOT/venv/bin/activate" ]; then
    echo ""
    echo -e "\033[0;31mERROR: Virtual environment not found.\033[0m"
    echo "Please run ./setup.sh first!"
    echo ""
    exit 1
fi

# Activate virtual environment
source "$PROJECT_ROOT/venv/bin/activate"

# Navigate to app directory and run the app
cd "$PROJECT_ROOT/app"

echo ""
echo "Starting RMBG-2-Studio..."
echo "The browser will open automatically when ready."
echo ""
echo "Press Ctrl+C to stop the server."
echo ""

python flask_app.py

echo ""
echo "Server stopped."
