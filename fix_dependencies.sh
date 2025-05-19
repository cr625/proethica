#!/bin/bash

# Script to fix dependency issues with Python packages
echo "Fixing Python dependencies..."

# Set Python to ignore the conda environment
export USE_CONDA="false"

# Add user site-packages to PYTHONPATH
export PYTHONPATH="/home/codespace/.local/lib/python3.12/site-packages:$PYTHONPATH"

# Force reinstall of all required packages
echo "Installing anthropic directly to user site-packages..."
pip install --user --force-reinstall anthropic

echo "Installing langchain packages..."
pip install --user --force-reinstall langchain-core langchain-anthropic langchain langchain-community

# Verify installation locations
echo -e "\nVerifying installation:"
echo "Checking anthropic..."
python -c "import anthropic; print(f'anthropic version: {anthropic.__version__} at {anthropic.__file__}')"

echo "Checking langchain_core..."
python -c "import langchain_core; print(f'langchain_core version: {langchain_core.__version__} at {langchain_core.__file__}')"

echo "Checking langchain_anthropic..."
python -c "import langchain_anthropic; print(f'langchain_anthropic version: {langchain_anthropic.__version__} at {langchain_anthropic.__file__}')"

echo -e "\nPython path:"
python -c "import sys; print('\n'.join(sys.path))"
