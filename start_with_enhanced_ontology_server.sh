#!/bin/bash
# Start ProEthica with Enhanced Ontology Server
# This script starts the ProEthica application using the enhanced ontology server
# with guidelines support instead of the unified ontology server.

# Set up error handling
set -e
echo "=== ProEthica Starter with Enhanced Ontology Server ==="

# Detect environment
if grep -q Microsoft /proc/version; then
    ENV_TYPE="wsl"
    CONTAINER_NAME="postgres17-pgvector-wsl"
    echo "Detected WSL environment..."
elif [[ "$OSTYPE" == "darwin"* ]]; then
    ENV_TYPE="mac"
    CONTAINER_NAME="postgres17-pgvector"
    echo "Detected MacOS environment..."
else
    ENV_TYPE="linux"
    CONTAINER_NAME="postgres17-pgvector"
    echo "Detected Linux environment..."
fi

echo "Using environment: $ENV_TYPE with container: $CONTAINER_NAME"

# Check if .env file exists
if [ -f .env ]; then
    source .env
    echo "Using existing USE_MOCK_FALLBACK setting from .env file"
else
    echo "Creating .env file..."
    cp .env.example .env
    echo "USE_MOCK_FALLBACK=false" >> .env
    echo "SET_CSRF_TOKEN_ON_PAGE_LOAD=true" >> .env
    source .env
fi

# Kill any existing MCP servers
echo "Checking for running MCP server processes..."
pkill -f "python.*run_enhanced_mcp_server_with_guidelines.py" || true
sleep 1

# Check Docker and PostgreSQL container
echo "Checking Docker and PostgreSQL container..."
if command -v docker &> /dev/null; then
    # Check if container exists
    if docker ps -a | grep -q $CONTAINER_NAME; then
        # Check if container is running
        if docker ps | grep -q $CONTAINER_NAME; then
            echo "PostgreSQL container '$CONTAINER_NAME' is already running on port 5433."
        else
            echo "Starting PostgreSQL container '$CONTAINER_NAME'..."
            docker start $CONTAINER_NAME
            sleep 3
            echo "PostgreSQL container started."
        fi
    else
        echo "PostgreSQL container '$CONTAINER_NAME' does not exist."
        echo "Please create the container first. See docs/docker_postgres_notes.md for details."
        exit 1
    fi
else
    echo "Docker not installed or not in PATH."
    echo "Assuming PostgreSQL is installed and running locally on port 5433."
fi

# Start the Enhanced Ontology MCP Server
echo "Starting Enhanced Ontology MCP Server..."

# Create logs directory if it doesn't exist
mkdir -p logs

# Get current datetime for log filename
LOG_DATE=$(date +%Y%m%d_%H%M%S)
LOG_FILE="logs/enhanced_ontology_server_$LOG_DATE.log"

# Start the server in the background
echo "Starting enhanced ontology MCP server on 0.0.0.0:5001"
python mcp/run_enhanced_mcp_server_with_guidelines.py > "$LOG_FILE" 2>&1 &
MCP_PID=$!

# Give the server time to start
sleep 3

# Check if the server started successfully
if ps -p $MCP_PID > /dev/null; then
    echo "Enhanced Ontology Server started successfully (PID: $MCP_PID)"
    echo "Log file: $LOG_FILE"
else
    echo "Failed to start the Enhanced Ontology Server. Check the logs: $LOG_FILE"
    cat "$LOG_FILE"
    exit 1
fi

# Initialize database schema
echo "Initializing database schema..."
if [ -f "scripts/schema_check.py" ]; then
    python scripts/schema_check.py
else
    echo "Schema check script not found, checking other locations..."
    if [ -f "scripts/database_migrations/check_schema.py" ]; then
        python scripts/database_migrations/check_schema.py
    elif [ -f "scripts/check_db.py" ]; then
        python scripts/check_db.py
    else
        echo "Warning: Could not find schema check script. Continuing anyway..."
    fi
fi

# Launch ProEthica
echo "Launching ProEthica with auto-detected environment: $ENV_TYPE"
echo "Setting MCP_SERVER_ALREADY_RUNNING=true to prevent starting duplicate MCP server"
export MCP_SERVER_ALREADY_RUNNING=true

echo "=== ProEthica Unified Launcher ==="
echo "Detected $ENV_TYPE environment"
echo "Starting in $ENV_TYPE mode using Flask dev server..."

# Check Docker PostgreSQL container status
echo "Checking Docker PostgreSQL container status..."
if command -v docker &> /dev/null && docker ps | grep -q $CONTAINER_NAME; then
    echo "Docker PostgreSQL container is running on port 5433."
else
    echo "Warning: Docker PostgreSQL container not detected."
    echo "Assuming PostgreSQL is installed and running locally."
fi

echo "Enhanced Ontology MCP server is running at http://localhost:5001"
echo "Starting Flask development server..."

# Source environment variables from .env
echo "=== Environment Variable Loader ==="
echo "Exporting environment variables from .env file..."

# Set MCP server URL explicitly
export MCP_SERVER_URL=http://localhost:5001
echo "Set MCP_SERVER_URL to http://localhost:5001"
echo "MCP server will be available at http://localhost:5001"

# Check enhanced MCP server status
echo "Checking enhanced MCP server status..."
echo "Testing connection to MCP server at http://localhost:5001/jsonrpc..."

# Test connection using curl
if curl -s -X POST http://localhost:5001/jsonrpc -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}' | grep -q jsonrpc; then
    echo "✓ MCP server is responding to JSON-RPC requests. Server is running properly!"
else
    echo "Warning: Could not verify MCP server is responding to JSON-RPC requests."
    echo "WARNING: MCP server may not be running properly. Continuing anyway..."
fi

# Run the Flask development server
python run.py

# Make sure to clean up the MCP server process on exit
cleanup() {
    echo "Shutting down MCP server..."
    kill $MCP_PID > /dev/null 2>&1 || true
    echo "Shutdown complete."
}

# Register cleanup function for process termination
trap cleanup EXIT

# Wait for user to press Ctrl+C
wait
