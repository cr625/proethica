#!/bin/bash
# Custom starter script for GitHub Codespaces environment

# Print banner
echo "=== ProEthica Codespace Custom Starter ==="
echo "Starting ProEthica with specific GitHub Codespaces configuration..."

# Set up PostgreSQL for GitHub Codespaces
echo "Setting up PostgreSQL for Codespaces environment..."
./scripts/setup_codespace_db.sh

# Make sure we have psycopg2
pip install psycopg2-binary >/dev/null 2>&1

# Check for running MCP server processes and kill them if found
echo "Checking for existing MCP server processes..."
pkill -f "python.*mcp/run_enhanced_mcp_server" || true
sleep 1

# Start the enhanced MCP server with guidelines support
echo "Starting Enhanced MCP Server with Guidelines Support..."
python mcp/run_enhanced_mcp_server_with_guidelines.py > logs/enhanced_ontology_server_codespace.log 2>&1 &
MCP_PID=$!
echo "Enhanced MCP Server started with PID: $MCP_PID"
echo "Logs being written to logs/enhanced_ontology_server_codespace.log"

# Wait for server to initialize
echo "Waiting for MCP server to initialize..."
sleep 3

# Test if MCP server is running properly
echo "Testing MCP server connectivity..."
curl -s -X POST http://localhost:5001/jsonrpc \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}' \
     > /dev/null

# Run the Codespace-specific Flask application
echo "Starting Flask application with Codespace configuration..."
echo "This script uses a special run configuration that properly handles imports and configuration"

# Export environment variables to ensure proper behavior
export FLASK_APP=codespace_run.py
export FLASK_ENV=development
export FLASK_DEBUG=1
export MCP_SERVER_ALREADY_RUNNING=true
export MCP_SERVER_URL=http://localhost:5001
export DATABASE_URL=postgresql://postgres:postgres@localhost:5433/ai_ethical_dm
export ENVIRONMENT=codespace

# Start the application using the Codespace-specific entry point
python codespace_run.py

# If the Flask app exits, kill the MCP server process
kill $MCP_PID 2>/dev/null || true
