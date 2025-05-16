#!/bin/bash
# Full ProEthica Web UI Launcher for GitHub Codespace
# This script starts all required services and launches the full web application

echo "=== ProEthica Full Web Application Launcher ==="
echo ""

# Kill any running processes to ensure a clean start
echo "Stopping any existing processes..."
pkill -f "python.*mcp/run_enhanced_mcp_server" || true
pkill -f "python.*codespace_run.py" || true
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
        pgvector/pgvector:pg17
    sleep 5
fi

# Create directories
mkdir -p logs

# Start MCP server
echo "Starting MCP server with guidelines support..."
python mcp/run_enhanced_mcp_server_with_guidelines.py > logs/mcp_server_web.log 2>&1 &
MCP_PID=$!
echo "MCP server started with PID: $MCP_PID"

# Wait for MCP server to initialize
echo "Waiting for MCP server to initialize..."
sleep 3

# Test MCP server
echo "Testing MCP server connection..."
if ! curl -s -X POST http://localhost:5001/jsonrpc \
     -H "Content-Type: application/json" \
     -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}' | grep -q "result"; then
    echo "Warning: MCP server not responding properly. Check logs/mcp_server_web.log for details."
else
    echo "MCP server is running and responding correctly."
fi

# Set environment variables
export FLASK_APP=app
export FLASK_ENV=development
export FLASK_DEBUG=1
export ENVIRONMENT="codespace"
export DATABASE_URL=postgresql://postgres:postgres@localhost:5433/ai_ethical_dm
export MCP_SERVER_URL=http://localhost:5001/jsonrpc
export CODESPACE=true

# Fix codespace_run.py if needed
if head -n 1 codespace_run.py | grep -q "^!"; then
    echo "Fixing codespace_run.py shebang..."
    sed -i '1s/^!/#!/' codespace_run.py
fi
chmod +x codespace_run.py

# Run the full application
echo ""
echo "Starting full ProEthica web application on port 3333..."
echo "When ready, access http://localhost:3333/ in your browser"
echo "You can also access the debug UI at http://localhost:5050/"
echo ""
python codespace_run.py --port 3333 --mcp-port 5001

# Clean up on exit
kill $MCP_PID 2>/dev/null || true
