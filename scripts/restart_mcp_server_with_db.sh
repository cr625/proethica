#!/bin/bash
# Script to restart the MCP server with database integration
# This script:
# 1. Stops any running MCP server instances
# 2. Starts a new MCP server with proper configuration

echo "Restarting MCP server with database integration..."

# Stop any running MCP servers
echo "Stopping running MCP server instances..."

# Find and kill MCP server processes
MCP_PIDS=$(ps aux | grep "http_ontology_mcp_server.py" | grep -v grep | awk '{print $2}')
if [ -n "$MCP_PIDS" ]; then
    echo "Found MCP server processes: $MCP_PIDS"
    echo "Killing processes..."
    kill -9 $MCP_PIDS
    echo "Processes killed."
else
    echo "No running MCP server processes found."
fi

# Clean up lock files
echo "Cleaning up lock files..."
if [ -f "/tmp/ontology_mcp_server.lock" ]; then
    rm /tmp/ontology_mcp_server.lock
    echo "Lock file removed."
else
    echo "No lock file found."
fi

# Start the MCP server
echo "Starting MCP server..."
MCP_DIR="$(dirname "$0")/../mcp"
MCP_LOG="$MCP_DIR/http_server.log"

cd "$(dirname "$0")/.."
python -u "$MCP_DIR/http_ontology_mcp_server.py" > "$MCP_LOG" 2>&1 &
MCP_PID=$!

echo "MCP server started with PID: $MCP_PID"
echo "Process is running in the background. Logs are available at: $MCP_LOG"

# Save the PID to a lock file
echo $MCP_PID > /tmp/ontology_mcp_server.lock
echo "PID saved to lock file: /tmp/ontology_mcp_server.lock"

# Wait for the server to initialize
echo "Waiting for server to initialize..."
sleep 3

# Verify the server is running
if ps -p $MCP_PID > /dev/null; then
    echo "MCP server is running."
    echo "You can check the logs with: tail -f $MCP_LOG"
else
    echo "ERROR: MCP server failed to start. Check the logs at: $MCP_LOG"
    exit 1
fi

echo "MCP server restart completed successfully."
