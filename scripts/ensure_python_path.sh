#!/bin/bash
#
# Script to ensure Python is using the correct site-packages paths for debugging

echo "Setting up Python environment for debugging..."

# Add user site-packages to PYTHONPATH
export PYTHONPATH="/home/codespace/.local/lib/python3.12/site-packages:$PYTHONPATH"
echo "PYTHONPATH set to: $PYTHONPATH"

# Disable the use of conda if needed
export USE_CONDA="false"
echo "USE_CONDA set to: $USE_CONDA"

# Print Python path info for debugging
echo "Python executable: $(which python)"
echo "Python version: $(python --version)"
echo "Python site packages:"
python -c "import site; print('\n'.join(site.getsitepackages()))"
echo "User site packages:"
python -c "import site; print(site.getusersitepackages())"
