#!/bin/bash
set -e

echo "=== REALM Starter ==="
echo "Starting REALM (Resource for Engineering And Learning Materials) application..."

# Setup shared PostgreSQL container
echo "Setting up shared PostgreSQL database..."
./scripts/setup_shared_postgres.sh

# Check if MSEO MCP server is already running
echo "Checking for running MSEO MCP server..."
if pgrep -f "mseo_mcp_server.py" > /dev/null; then
  echo "MSEO MCP server is already running."
else
  echo "Starting MSEO MCP server on port 8078..."
  
  # Create log directory if it doesn't exist
  mkdir -p logs
  
  # Start the MSEO MCP server in the background
  python mcp/mseo/run_mseo_mcp_server.py > logs/mseo_mcp_server.log 2>&1 &
  
  # Wait for server to start up
  echo "Waiting for MSEO MCP server to initialize..."
  sleep 3
fi

# Set environment variables for REALM
export FLASK_APP=run_realm.py
export FLASK_ENV=development
export MSEO_SERVER_URL=http://localhost:8078
export REALM_DATABASE_URL=postgresql://postgres:PASS@localhost:5433/realm

# Start the REALM application
echo "Starting REALM application..."
python run_realm.py
