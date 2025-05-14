#!/bin/bash
# Simple starter script for using the modified codespace environment
# This script handles both the database and MCP server setup

# Print banner
echo "=== ProEthica Codespace Simple Starter ==="

# Kill any running processes
echo "Stopping any running MCP servers..."
pkill -f "python.*mcp/run_enhanced_mcp_server" || true
sleep 1

# Make sure PostgreSQL credentials are correct in .env
echo "Checking .env file for database connection..."
grep -q "postgres:postgres@localhost" .env || {
    echo "Updating database credentials in .env..."
    sed -i 's/postgres:[^@]*@localhost/postgres:postgres@localhost/' .env
}

# Check for running PostgreSQL container
echo "Checking for PostgreSQL docker container..."
CONTAINER_ID=$(docker ps -q -f name=postgres17-pgvector-codespace)

if [ -z "$CONTAINER_ID" ]; then
    echo "PostgreSQL container not found, creating a new one..."
    docker run -d --name postgres17-pgvector-codespace \
        -e POSTGRES_PASSWORD=postgres \
        -p 5433:5432 \
        postgres:17-bookworm
    
    echo "Waiting for PostgreSQL to initialize..."
    sleep 5
    
    # Create the database
    echo "Creating database..."
    docker exec -it postgres17-pgvector-codespace psql -U postgres -c "CREATE DATABASE ai_ethical_dm;" || true
else
    echo "PostgreSQL container is already running with ID: $CONTAINER_ID"
fi

# Ensure database connection working
echo "Testing database connection..."
docker exec -it postgres17-pgvector-codespace psql -U postgres -c "\l" | grep -q "ai_ethical_dm" || {
    echo "Creating database..."
    docker exec -it postgres17-pgvector-codespace psql -U postgres -c "CREATE DATABASE ai_ethical_dm;" || true
}

# Create logs directory
echo "Ensuring logs directory exists..."
mkdir -p logs

# Start MCP server
echo "Starting MCP server..."
python mcp/run_enhanced_mcp_server_with_guidelines.py > logs/mcp_server_codespace.log 2>&1 &
MCP_PID=$!
echo "MCP server started with PID: $MCP_PID"

# Wait for server to initialize
echo "Waiting for MCP server to initialize..."
sleep 3

# Test MCP server connection
echo "Testing MCP server connection..."
curl -s -X POST http://localhost:5001/jsonrpc \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}' || {
    echo "Warning: MCP server did not respond correctly"
}

# Set environment variables
echo "Setting environment variables..."
export FLASK_APP=modified_codespace_env.py
export FLASK_ENV=development
export FLASK_DEBUG=1
export DATABASE_URL=postgresql://postgres:postgres@localhost:5433/ai_ethical_dm
export ENVIRONMENT=codespace
export MCP_SERVER_ALREADY_RUNNING=true
export MCP_SERVER_URL=http://localhost:5001

# Start the application
echo "Starting Flask application..."
python ./modified_codespace_env.py

# Clean up when app exits
kill $MCP_PID 2>/dev/null || true
