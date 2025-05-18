#!/bin/bash
# Restart script for the MCP Server

echo "Restarting MCP Server..."

# Kill any existing MCP server processes
echo "Stopping any existing MCP servers..."
pkill -f "python.*mcp.*server" || echo "No matching processes found"

# Wait a moment for ports to be freed
sleep 2

# Set database-related environment variables
export DATABASE_URL="postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"

# Make sure the database config is set for Flask
echo "Starting new MCP server..."
cd /workspaces/ai-ethical-dm
chmod +x run_http_mcp_server.sh
./run_http_mcp_server.sh

# Verify server is running
echo "Checking server health..."
sleep 2
curl -s http://localhost:5001/health || echo "Server health check failed"
