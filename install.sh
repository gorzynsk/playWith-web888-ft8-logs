#!/bin/bash

# Check if the virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Virtual environment not found. Creating .venv..."
    python3 -m venv .venv
else
    echo "Virtual environment found. Skipping creation."
fi

# Activate the virtual environment
echo "Activating the virtual environment..."
source .venv/bin/activate

# Install the required packages from requirements.txt
echo "Installing required modules from requirements.txt..."
pip install --upgrade pip
pip install -r requirements.txt

echo "Installation complete!"

