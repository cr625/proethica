#!/bin/bash

echo "==============================================="
echo "Setting up AI-Ethical-DM Development Environment"
echo "==============================================="

# Disable conda to avoid environment conflicts
export USE_CONDA="false"
echo "Disabled conda environment usage"

# Add user site-packages to PYTHONPATH
export PYTHONPATH="/home/codespace/.local/lib/python3.12/site-packages:$PYTHONPATH"
echo "Added user site-packages to PYTHONPATH"

# Install the exact Anthropic version first to ensure it's prioritized
echo -e "\nInstalling Anthropic SDK v0.51.0..."
pip install --user --force-reinstall anthropic==0.51.0

# Install all other dependencies from consolidated requirements
echo -e "\nInstalling all dependencies from consolidated requirements..."
pip install --user -r consolidated_requirements.txt

# Create a .env file if it doesn't exist (with ANTHROPIC_API_KEY placeholder)
if [ ! -f .env ]; then
    echo -e "\nCreating .env file..."
    cp .env.example .env
    echo "Created .env file from example"
fi

# Check if ANTHROPIC_API_KEY is in the .env file
if ! grep -q "ANTHROPIC_API_KEY" .env; then
    echo "ANTHROPIC_API_KEY=YOUR_KEY_HERE" >> .env
    echo "Added ANTHROPIC_API_KEY placeholder to .env file"
fi

# Verify installations
echo -e "\n==============================================="
echo "Verifying critical installations:"
echo "==============================================="

# Verify Anthropic installation
echo -e "\nChecking Anthropic SDK:"
if python -c "import anthropic; print(f'✅ anthropic v{anthropic.__version__} installed at {anthropic.__file__}')"; then
    # Test Anthropic client initialization
    echo -e "\nTesting Anthropic client initialization:"
    python -c "import anthropic; client = anthropic.Anthropic(); print('✅ Anthropic client initialized successfully'); print(f'Available client methods: {[m for m in dir(client) if not m.startswith(\"_\")][0:10]}...')"
else
    echo "❌ Failed to import Anthropic SDK"
fi

# Verify langchain-anthropic installation
echo -e "\nChecking langchain-anthropic:"
if python -c "import langchain_anthropic; print(f'✅ langchain_anthropic installed')"; then 
    echo "Successfully imported langchain_anthropic"
else
    echo "❌ Failed to import langchain_anthropic"
fi

# Verify langchain-core installation
echo -e "\nChecking langchain-core:"
if python -c "import langchain_core; print(f'✅ langchain_core v{langchain_core.__version__} installed')"; then
    echo "Successfully imported langchain_core"
else
    echo "❌ Failed to import langchain_core"
fi

echo -e "\n==============================================="
echo "Environment setup complete!"
echo "==============================================="

# Print guidance message
echo -e "\nNOTE: If you need to use this environment in other terminals:"
echo "1. Run 'source setup_environment.sh' to set up the environment variables"
echo "2. Make sure your .env file has a valid ANTHROPIC_API_KEY"
echo -e "\nTo test the Anthropic integration, run: python test_anthropic_integration.py"
