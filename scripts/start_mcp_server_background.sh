#!/bin/bash
# Start the MCP server in the background
echo "Starting MCP server in the background..."
nohup python mcp/run_enhanced_mcp_server_with_guidelines.py > mcp_server.log 2>&1 &
MCP_PID=$!
echo "MCP server started with PID: $MCP_PID"
echo "Waiting for MCP server to initialize (5 seconds)..."
sleep 5
echo "MCP server should be running now at http://localhost:5001"
echo "Check mcp_server.log for output"
