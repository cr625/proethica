#!/bin/bash
# Debug script for running the application with proper debugging setup

echo "Applying SQLAlchemy URL fix patch..."
python patch_sqlalchemy_url.py

echo "Setting environment variables..."
export ENVIRONMENT=codespace
export DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm
export SQLALCHEMY_DATABASE_URI=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm
export MCP_SERVER_URL=http://localhost:5001
export MCP_SERVER_ALREADY_RUNNING=true
export FLASK_DEBUG=1

echo "Running application..."
python run.py --port 3333 --mcp-port 5001

# This script will not reach this point unless the app crashes
echo "Application terminated."
