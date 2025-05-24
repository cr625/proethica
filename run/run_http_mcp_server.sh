#!/bin/bash
# Script to run the HTTP Ontology MCP Server

echo "Starting HTTP Ontology MCP Server..."

# Set database-related environment variables
export DATABASE_URL="postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"

# Run the MCP server
python3 -m mcp.http_ontology_mcp_server

echo "Server should be running at http://localhost:5001"
echo "Run ./test_ontology_loading.py to verify the fix"
