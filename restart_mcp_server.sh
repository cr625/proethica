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
export USE_MOCK_GUIDELINE_RESPONSES=false

# Make sure the database config is set for Flask
echo "Starting new MCP server..."
cd /workspaces/ai-ethical-dm
python mcp/run_enhanced_mcp_server_with_guidelines.py &

# Verify server is running
echo "Checking server health..."
sleep 2
curl -s http://localhost:5001/health || echo "Server health check failed"
