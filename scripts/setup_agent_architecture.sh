#!/bin/bash
# Setup script for the agent-based architecture
# This script installs the required dependencies and sets up the agent-based architecture

set -e  # Exit on error

echo "Setting up agent-based architecture..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Check if langchain-anthropic is installed
if ! pip list | grep -q "langchain-anthropic"; then
    echo "Installing langchain-anthropic..."
    pip install langchain-anthropic
fi

# Create necessary directories
echo "Creating necessary directories..."
mkdir -p app/services/agents

# Check if the agent files exist
if [ ! -f "app/services/agents/__init__.py" ]; then
    echo "Agent files not found. Please run the setup script again after ensuring the agent files are in place."
    exit 1
fi

# Check if python-dotenv is installed
if ! pip list | grep -q "python-dotenv"; then
    echo "Installing python-dotenv..."
    pip install python-dotenv
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. Make sure you have an .env file with ANTHROPIC_API_KEY set."
    echo "You can copy .env.example to .env and add your API key."
    echo "cp .env.example .env"
    echo "Then edit .env to add your ANTHROPIC_API_KEY."
fi

echo "Agent-based architecture setup complete!"
echo ""
echo "To run the application with the agent orchestrator enabled, use:"
echo "  ./scripts/run_with_agents.py"
echo ""
echo "To test the agent orchestrator, use:"
echo "  ./scripts/test_guidelines_agent.py"
echo ""
echo "For more information, see docs/agent_based_architecture.md"
