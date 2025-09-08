#!/bin/bash
"""
ProEthica Services Startup Script
Starts OntServe MCP server and ProEthica Flask application
"""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${GREEN}Starting ProEthica Services...${NC}"

# Function to check if a port is in use
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0  # Port is in use
    else
        return 1  # Port is free
    fi
}

# Function to wait for service to be ready
wait_for_service() {
    local service_name=$1
    local port=$2
    local max_attempts=30
    local attempt=0
    
    echo -e "${YELLOW}Waiting for $service_name on port $port...${NC}"
    
    while [ $attempt -lt $max_attempts ]; do
        if check_port $port; then
            echo -e "${GREEN}✓ $service_name is ready on port $port${NC}"
            return 0
        fi
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done
    
    echo -e "${RED}✗ $service_name failed to start on port $port${NC}"
    return 1
}

# Activate virtual environment if it exists
if [ -f "$PROJECT_ROOT/venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source "$PROJECT_ROOT/venv/bin/activate"
elif [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
    echo "Activating virtual environment..."
    source "$PROJECT_ROOT/.venv/bin/activate"
fi

# Check and start OntServe MCP Server
MCP_PORT=${ONTSERVE_MCP_PORT:-8082}
echo -e "${YELLOW}Checking OntServe MCP Server on port $MCP_PORT...${NC}"

if check_port $MCP_PORT; then
    echo -e "${GREEN}✓ OntServe MCP Server is already running on port $MCP_PORT${NC}"
else
    echo -e "${YELLOW}Starting OntServe MCP Server...${NC}"
    
    # Start MCP server in background
    cd "$PROJECT_ROOT/OntServe"
    python servers/mcp_server.py &
    MCP_PID=$!
    
    # Wait for MCP server to be ready
    if wait_for_service "OntServe MCP Server" $MCP_PORT; then
        echo -e "${GREEN}✓ OntServe MCP Server started (PID: $MCP_PID)${NC}"
        echo $MCP_PID > "$PROJECT_ROOT/proethica/.mcp_server.pid"
    else
        echo -e "${RED}Failed to start OntServe MCP Server${NC}"
        kill $MCP_PID 2>/dev/null
        exit 1
    fi
fi

# Health check for MCP server
echo -e "${YELLOW}Performing MCP server health check...${NC}"
HEALTH_CHECK=$(curl -s http://localhost:$MCP_PORT/health 2>/dev/null)
if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ MCP server health check passed${NC}"
else
    echo -e "${YELLOW}⚠ MCP server health check failed, but continuing...${NC}"
fi

# Start ProEthica Flask Application
FLASK_PORT=${FLASK_PORT:-5000}
echo -e "${YELLOW}Starting ProEthica Flask application on port $FLASK_PORT...${NC}"

cd "$PROJECT_ROOT/proethica"

# Export environment variables for ProEthica to know MCP is available
export ONTSERVE_MCP_ENABLED=true
export ONTSERVE_MCP_URL="http://localhost:$MCP_PORT"

# Check if we should run in debug mode
if [ "$1" == "--debug" ] || [ "$DEBUG" == "true" ]; then
    echo -e "${YELLOW}Starting ProEthica in DEBUG mode${NC}"
    export DEBUG=true
    python run.py
else
    echo -e "${YELLOW}Starting ProEthica in PRODUCTION mode${NC}"
    # For production, use gunicorn
    if command -v gunicorn &> /dev/null; then
        gunicorn --bind 0.0.0.0:$FLASK_PORT --workers 4 wsgi:application
    else
        echo -e "${YELLOW}Gunicorn not found, using development server${NC}"
        python run.py
    fi
fi
