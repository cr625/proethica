#!/bin/bash
# Ultra-simplified starter script for ProEthica in codespace
# This script avoids all template issues and interactive prompts

# Print banner
echo "=== ProEthica Codespace Ultra-Simple Starter ==="

# Kill any running processes
echo "Stopping any running Python processes..."
pkill -f "python.*mcp/run_enhanced_mcp_server" || true
pkill -f "python.*modified_codespace_env.py" || true
pkill -f "python.*simplified_debug_app.py" || true
sleep 1

# Make sure PostgreSQL credentials are correct
echo "Ensuring database credentials are correct..."
sed -i 's/postgres:[^@]*@localhost/postgres:postgres@localhost/' .env

# Check PostgreSQL container 
echo "Checking PostgreSQL container..."
if ! docker ps | grep -q postgres17-pgvector-codespace; then
    echo "Starting PostgreSQL container..."
    docker start postgres17-pgvector-codespace || \
    docker run -d --name postgres17-pgvector-codespace \
        -e POSTGRES_PASSWORD=postgres \
        -p 5433:5432 \
        postgres:17-bookworm
    sleep 5
fi

# Create directories
mkdir -p logs

# Start MCP server
echo "Starting MCP server..."
python mcp/run_enhanced_mcp_server_with_guidelines.py > logs/mcp_server.log 2>&1 &
sleep 3

# Set environment variables
export FLASK_APP=simplified_debug_app.py
export FLASK_ENV=development
export FLASK_DEBUG=1
export DATABASE_URL=postgresql://postgres:postgres@localhost:5433/ai_ethical_dm
export MCP_SERVER_URL=http://localhost:5001/jsonrpc

# Start the simplified debug application - much more reliable
echo "Starting simplified debug application..."
echo "When ready, access http://localhost:5050/ in your browser"
python ./simplified_debug_app.py
