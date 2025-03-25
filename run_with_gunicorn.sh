#!/bin/bash
# Run the application with Gunicorn for better stability
# Usage: ./run_with_gunicorn.sh

# Set the number of worker processes
WORKERS=4

# Set the timeout (in seconds)
# This is increased from the default 30 seconds to accommodate longer processing times
TIMEOUT=120

# Restart the MCP server
echo "Restarting the MCP server..."
./scripts/restart_mcp_server.sh

# Wait for the MCP server to start
echo "Waiting for the MCP server to start..."
sleep 5  # Increased wait time to ensure MCP server is fully initialized

# Set the MCP server URL environment variable
export MCP_SERVER_URL="http://localhost:5000"
echo "Set MCP_SERVER_URL to $MCP_SERVER_URL"

# Run Gunicorn with the specified settings
echo "Starting AI Ethical DM with Gunicorn ($WORKERS workers, $TIMEOUT second timeout)..."
gunicorn -w $WORKERS -t $TIMEOUT "app:create_app()" --bind 127.0.0.1:8000
