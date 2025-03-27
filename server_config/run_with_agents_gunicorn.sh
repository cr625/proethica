#!/bin/bash
# Run the application with Gunicorn and agent orchestrator enabled
# Usage: ./run_with_agents_gunicorn.sh

# Set the number of worker processes
WORKERS=3

# Set the timeout (in seconds)
# This is increased from the default 30 seconds to accommodate longer processing times
TIMEOUT=120

# Restart the MCP server
echo "Restarting the MCP server..."
./scripts/restart_mcp_server_gunicorn.fixed.sh

# Wait for the MCP server to start
echo "Waiting for the MCP server to start..."
sleep 5  # Increased wait time to ensure MCP server is fully initialized

# Set the MCP server URL environment variable
export MCP_SERVER_URL="http://localhost:5001"
echo "Set MCP_SERVER_URL to $MCP_SERVER_URL"

# Set environment variable to enable agent orchestrator
export USE_AGENT_ORCHESTRATOR="true"
echo "Enabled agent orchestrator"

# Run Gunicorn with the specified settings
echo "Starting AI Ethical DM with Gunicorn ($WORKERS workers, $TIMEOUT second timeout) and agent orchestrator..."
# Pass environment variables to Gunicorn workers
gunicorn -w $WORKERS -t $TIMEOUT "app:create_app('production')" --bind 127.0.0.1:5000 \
  --env MCP_SERVER_URL=$MCP_SERVER_URL \
  --env USE_AGENT_ORCHESTRATOR=$USE_AGENT_ORCHESTRATOR \
  --log-level debug
