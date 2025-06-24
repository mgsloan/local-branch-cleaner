#!/bin/bash

set -e

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

# Check if venv was created successfully
if [ ! -f "venv/bin/pip" ]; then
    echo -e "${RED}❌ Error: Failed to create virtual environment${NC}"
    echo "Please ensure python3-venv is installed: sudo apt install python3-venv"
    exit 1
fi

# Use the virtual environment's pip directly to avoid activation issues
echo "Installing backend dependencies..."
"$SCRIPT_DIR/backend/venv/bin/python" -m pip install --upgrade pip
"$SCRIPT_DIR/backend/venv/bin/pip" install -r requirements.txt
