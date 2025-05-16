#!/bin/bash
# Reliable launcher for ProEthica in GitHub Codespace
# Handles database initialization, MCP server, and web UI

# Print banner
echo "====================================================="
echo "       ProEthica Codespace Launcher v2.0             "
echo "====================================================="

# Terminate any active processes to ensure clean start
echo "Stopping any running Python processes..."
pkill -f "python.*mcp/run_enhanced_mcp_server" 2>/dev/null || true
pkill -f "python.*codespace_run.py" 2>/dev/null || true
pkill -f "python.*simplified_debug_app.py" 2>/dev/null || true
sleep 1

# Create required directories
mkdir -p logs

# Check Docker container
echo "Checking PostgreSQL container..."
if ! docker ps | grep -q postgres17-pgvector-codespace; then
    echo "Starting PostgreSQL container..."
    docker start postgres17-pgvector-codespace 2>/dev/null || \
    docker run -d --name postgres17-pgvector-codespace \
        -e POSTGRES_PASSWORD=postgres \
        -p 5433:5432 \
        pgvector/pgvector:pg17
    # Wait for container to fully start
    echo "Waiting for PostgreSQL to initialize..."
    sleep 3
fi

# Initialize database with proper timeouts and retries
echo "Initializing database (with retries)..."
python codespace_run_db.py
if [ ! -f .db_initialized ]; then
    echo "Failed to initialize database. Please check logs."
    exit 1
fi

# Set environment variables
export FLASK_ENV=development
export FLASK_DEBUG=1
export ENVIRONMENT="codespace"
export DATABASE_URL=postgresql://postgres:postgres@localhost:5433/ai_ethical_dm
export MCP_SERVER_URL=http://localhost:5001/jsonrpc

# Start MCP server
echo "Starting MCP server with guidelines support..."
python mcp/run_enhanced_mcp_server_with_guidelines.py > logs/mcp_server.log 2>&1 &
MCP_PID=$!
echo "MCP server started with PID: $MCP_PID"

# Wait for MCP server to initialize
echo "Waiting for MCP server to initialize..."
sleep 3

# Start simplified debug server for reliability checking
echo "Starting simplified debug application..."
python simplified_debug_app.py > logs/debug_app.log 2>&1 &
DEBUG_PID=$!
echo "Debug app started with PID: $DEBUG_PID"

# Ensure debug server is ready
echo "Waiting for debug app to initialize..."
sleep 3

# Check if services are running correctly
echo "Checking system status..."
if curl -s http://localhost:5050/api/status | grep -q '"connected": true'; then
    echo "✅ Debug service is running correctly!"
else
    echo "⚠️ Debug service may have issues. Check logs/debug_app.log for details."
fi

echo ""
echo "====================================================="
echo "            ProEthica System is Running              "
echo "====================================================="
echo "Debug interface: http://localhost:5050/"
echo "MCP server: http://localhost:5001/jsonrpc"
echo ""
echo "Running the full web application is optional:"
echo "You can now run: python codespace_run.py"
echo ""
echo "Press Ctrl+C to stop all services"
echo "====================================================="

# Wait for user interrupt
trap "echo 'Stopping services...'; kill $MCP_PID $DEBUG_PID 2>/dev/null; echo 'Services stopped.'" INT
wait
