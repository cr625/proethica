#!/bin/bash
# start_proethica.sh
#
# Convenience script to start the ProEthica application with all services
# properly configured.

set -e  # Exit on error

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== ProEthica Starter ===${NC}"
echo -e "${YELLOW}Starting ProEthica with all services enabled...${NC}"

# Check if auto_run.sh exists and is executable
if [ ! -f "./auto_run.sh" ]; then
    echo -e "${RED}ERROR: auto_run.sh not found!${NC}"
    echo -e "${YELLOW}This script must be run from the ProEthica root directory.${NC}"
    exit 1
fi

if [ ! -x "./auto_run.sh" ]; then
    echo -e "${YELLOW}Making auto_run.sh executable...${NC}"
    chmod +x ./auto_run.sh
fi

# Optional: Check if .env exists and contains MCP_SERVER_URL
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}No .env file found. Creating one from .env.example...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}Adding MCP_SERVER_URL to .env file...${NC}"
    echo "MCP_SERVER_URL=http://localhost:5001" >> .env
    echo "USE_MOCK_FALLBACK=true" >> .env
else
    # Update existing .env file with correct MCP_SERVER_URL and USE_MOCK_FALLBACK
    if ! grep -q "MCP_SERVER_URL=" .env; then
        echo -e "${YELLOW}Adding MCP_SERVER_URL to .env file...${NC}"
        echo "MCP_SERVER_URL=http://localhost:5001" >> .env
    else
        # Update existing MCP_SERVER_URL to use port 5001
        sed -i "s|MCP_SERVER_URL=http://localhost:[0-9]*|MCP_SERVER_URL=http://localhost:5001|g" .env
    fi
    
    if ! grep -q "USE_MOCK_FALLBACK=" .env; then
        echo -e "${YELLOW}Adding USE_MOCK_FALLBACK to .env file...${NC}"
        echo "USE_MOCK_FALLBACK=true" >> .env
    else
        sed -i "s/USE_MOCK_FALLBACK=.*/USE_MOCK_FALLBACK=true/" .env
    fi
fi

# Ensure HTTP MCP server script is executable
if [ ! -x "./scripts/restart_http_mcp_server.sh" ]; then
    echo -e "${YELLOW}Making restart_http_mcp_server.sh executable...${NC}"
    chmod +x ./scripts/restart_http_mcp_server.sh
fi

# Check for WSL environment
if grep -qi microsoft /proc/version; then
    echo -e "${BLUE}Detected WSL environment...${NC}"
    
    # Check if native PostgreSQL is running and stop it if needed
    if command -v service &> /dev/null && service postgresql status &> /dev/null; then
        echo -e "${YELLOW}Native PostgreSQL is running in WSL. Stopping it to avoid port conflicts...${NC}"
        sudo service postgresql stop || echo -e "${RED}Could not stop PostgreSQL service. You may experience port conflicts.${NC}"
    fi
fi

# Check if Docker is installed and running
echo -e "${BLUE}Checking Docker and PostgreSQL container...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed or not in PATH. Please install Docker to use the PostgreSQL container.${NC}"
    echo -e "${YELLOW}Continuing without Docker verification, but database connection may fail...${NC}"
else
    # Check if PostgreSQL container exists and is running
    POSTGRES_CONTAINER="postgres17-pgvector"
    
    # Extract database connection details from .env file
    DB_PORT=$(grep "DATABASE_URL" .env | sed -E 's/.*localhost:([0-9]+).*/\1/')
    
    if [ -z "$DB_PORT" ]; then
        DB_PORT="5433"  # Default port if not found in .env
    fi
    
    CONTAINER_STATUS=$(docker ps -a --filter "name=$POSTGRES_CONTAINER" --format "{{.Status}}")
    
    if [ -z "$CONTAINER_STATUS" ]; then
        echo -e "${RED}PostgreSQL container '$POSTGRES_CONTAINER' not found.${NC}"
        echo -e "${YELLOW}Please create the container with: docker run -d --name $POSTGRES_CONTAINER -p $DB_PORT:5432 -e POSTGRES_PASSWORD=PASS -e POSTGRES_DB=ai_ethical_dm pgvector/pgvector:pg17${NC}"
        echo -e "${YELLOW}Continuing without Docker PostgreSQL, but database connection may fail...${NC}"
    else
        if [[ $CONTAINER_STATUS == Exited* ]] || [[ $CONTAINER_STATUS == Created* ]]; then
            echo -e "${YELLOW}PostgreSQL container '$POSTGRES_CONTAINER' exists but is not running. Starting it now...${NC}"
            if docker start $POSTGRES_CONTAINER; then
                echo -e "${GREEN}PostgreSQL container started successfully on port $DB_PORT.${NC}"
                # Wait a moment for PostgreSQL to initialize
                echo -e "${YELLOW}Waiting for PostgreSQL to initialize...${NC}"
                sleep 3
            else
                echo -e "${RED}Failed to start PostgreSQL container. Please check Docker logs.${NC}"
                echo -e "${YELLOW}Continuing anyway, but database connection may fail...${NC}"
            fi
        else
            echo -e "${GREEN}PostgreSQL container '$POSTGRES_CONTAINER' is already running on port $DB_PORT.${NC}"
        fi
    fi
fi

# Ensure run_with_env.sh is executable
if [ -f "./scripts/run_with_env.sh" ] && [ ! -x "./scripts/run_with_env.sh" ]; then
    echo -e "${YELLOW}Making run_with_env.sh executable...${NC}"
    chmod +x ./scripts/run_with_env.sh
fi

# Check run_with_env.sh existence and inform about it
if [ -f "./scripts/run_with_env.sh" ] && [ -x "./scripts/run_with_env.sh" ]; then
    echo -e "${GREEN}Found run_with_env.sh utility for proper environment variable handling.${NC}"
    echo -e "${BLUE}This ensures Anthropic SDK and other APIs work correctly.${NC}"
fi

# Launch the application with auto_run.sh
echo -e "${GREEN}Launching ProEthica with auto-detected environment...${NC}"
./auto_run.sh
