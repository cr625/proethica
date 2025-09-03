#!/bin/bash
# Script to run scenario generation diagnosis
# This avoids the shell execution issues you mentioned

echo "🚀 Running ProEthica Scenario Generation Diagnosis..."
echo "=================================================="

# Change to the proethica directory
cd "$(dirname "$0")"

# Check if virtual environment exists and activate it
if [ -f "../setup-venv.sh" ]; then
    echo "🔧 Setting up virtual environment..."
    source ../setup-venv.sh
fi

# Set PYTHONPATH to include current directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Run the diagnostic script
python test_scenario_generation_diagnosis.py

echo ""
echo "=================================================="
echo "✨ Diagnosis complete. Check results above."
