#!/bin/bash
echo "Checking for running Python MCP server processes..."
ps -ef | grep "python.*mcp/run_enhanced_mcp_server" | grep -v grep || echo "No MCP server processes found"

echo "Checking docker container status..."
docker ps | grep postgres || echo "No postgres containers running"

echo "Testing database connection..."
PGPASSWORD=postgres psql -h localhost -p 5433 -U postgres -c "\l" || echo "Database connection failed"

echo "Testing MCP server connection..."
curl -s -X POST http://localhost:5001/jsonrpc \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}' || echo "MCP server connection failed"
