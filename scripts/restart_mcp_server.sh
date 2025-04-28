#!/bin/bash
# Restart script for the enhanced MCP ontology server

# Kill any existing MCP server processes
echo "Stopping any existing MCP server processes..."
pkill -f "python3 mcp/run_enhanced_mcp_server.py" || true
sleep 1

# Start the enhanced MCP server in the background
echo "Starting enhanced MCP server..."
python3 mcp/run_enhanced_mcp_server.py &

# Wait a moment to ensure server has time to start
sleep 2
echo "Enhanced MCP server has been restarted."
