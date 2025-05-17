#!/bin/bash

# run_with_live_llm.sh
# Script to run the AI-Ethical-DM system with live LLM integration (no mock responses)

set -e

echo "=========================================================="
echo " ProEthica AI-Ethical-DM with LIVE LLM Integration"
echo "=========================================================="
echo ""
echo "This script will start the system with live LLM integration"
echo "for guideline concept extraction (no mock responses)."
echo ""
echo "Please choose an option:"
echo "1) Start MCP server first, then Flask app in separate terminal"
echo "2) Start Flask app directly (assuming MCP server is running)"
echo "3) Exit"
echo ""
read -p "Enter your choice (1-3): " choice

case $choice in
  1)
    echo ""
    echo "Starting MCP Server with LIVE LLM integration..."
    export USE_MOCK_GUIDELINE_RESPONSES=false
    
    # Start MCP server in a new terminal
    gnome-terminal -- bash -c "export USE_MOCK_GUIDELINE_RESPONSES=false && python mcp/run_enhanced_mcp_server_with_guidelines.py; exec bash" || \
    xterm -e "export USE_MOCK_GUIDELINE_RESPONSES=false && python mcp/run_enhanced_mcp_server_with_guidelines.py; exec bash" || \
    Terminal.app -e "export USE_MOCK_GUIDELINE_RESPONSES=false && python mcp/run_enhanced_mcp_server_with_guidelines.py; exec bash" || \
    echo "Could not open a new terminal window. Starting MCP server in background."
    
    echo "Waiting 5 seconds for MCP server to initialize..."
    sleep 5
    
    # Verify MCP server is running
    curl -s http://localhost:5001/health > /dev/null
    if [ $? -ne 0 ]; then
      echo "WARNING: MCP server may not be running correctly. Starting Flask app anyway..."
    else
      echo "MCP server is running."
    fi
    
    # Start Flask app
    echo ""
    echo "Starting Flask application..."
    export USE_MOCK_GUIDELINE_RESPONSES=false
    export FLASK_APP=app
    export FLASK_ENV=development
    export FLASK_DEBUG=1
    export MCP_SERVER_URL=http://localhost:5001
    
    # Set database URL for SQLAlchemy
    export DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm
    export SQLALCHEMY_TRACK_MODIFICATIONS=false
    
    python run_debug_app.py
    ;;
    
  2)
    # Start Flask app only
    echo ""
    echo "Starting Flask application with LIVE LLM integration..."
    echo "(Make sure MCP server is already running)"
    
    export USE_MOCK_GUIDELINE_RESPONSES=false
    export FLASK_APP=app
    export FLASK_ENV=development
    export FLASK_DEBUG=1
    export MCP_SERVER_URL=http://localhost:5001
    
    # Set database URL for SQLAlchemy
    export DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm
    export SQLALCHEMY_TRACK_MODIFICATIONS=false
    
    python run_debug_app.py
    ;;
    
  3)
    echo "Exiting."
    exit 0
    ;;
    
  *)
    echo "Invalid option. Exiting."
    exit 1
    ;;
esac
