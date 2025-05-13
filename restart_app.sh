#!/bin/bash

# Kill all existing Python processes
echo "Stopping existing Python processes..."
pkill -f "python run.py" || echo "No Python processes found"
pkill -f "run_enhanced_mcp_server" || echo "No MCP server processes found"

# Wait a moment for processes to stop
sleep 2

# Start the application again
echo "Starting ProEthica application..."
./start_proethica_updated.sh
