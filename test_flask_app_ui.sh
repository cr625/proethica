#!/bin/bash

# test_flask_app_ui.sh
# Script to test the full Flask app UI with proper configuration

echo "=========================================================="
echo " Testing Flask App UI with Full Configuration"
echo "=========================================================="
echo ""

# Load environment variables from .env file if it exists
if [ -f .env ]; then
    echo "Loading environment variables from .env file"
    set -a
    source .env
    set +a
fi

# Set critical environment variables
export USE_MOCK_GUIDELINE_RESPONSES=false
export ENVIRONMENT=development
export MCP_SERVER_PORT=5001
export MCP_SERVER_URL=http://localhost:5001
export DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm
export SQLALCHEMY_TRACK_MODIFICATIONS=false
export FLASK_APP=app
export FLASK_ENV=development
export FLASK_DEBUG=1

echo ""
echo "Starting MCP Server in the background..."
python mcp/run_enhanced_mcp_server_with_guidelines.py > mcp_server.log 2>&1 &
MCP_PID=$!

echo "Waiting 5 seconds for MCP server to initialize..."
sleep 5

echo ""
echo "Starting Flask application with fixed configuration..."
echo "This should show the FULL application UI with all routes available."
echo ""
echo "Once the server starts, open your browser and visit:"
echo "   http://localhost:3333"
echo ""
echo "You should see a complete navigation menu with access to all features."
echo "Press Ctrl+C to stop the server when done testing."
echo ""

python run_debug_app.py

# Cleanup MCP server when Flask app exits
kill $MCP_PID
