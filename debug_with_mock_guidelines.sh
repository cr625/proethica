#!/bin/bash
# Enable mock guideline responses for faster development and testing

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Export environment variable to enable mock responses
export USE_MOCK_GUIDELINE_RESPONSES=true

# Display instructions for running with mock responses
echo -e "${BLUE}====================================================${NC}"
echo -e "${YELLOW}MOCK GUIDELINE RESPONSES - DEVELOPMENT MODE ACTIVATED${NC}"
echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}This mode uses pre-loaded concept data instead of calling the LLM API${NC}"

# Detect environment and set PostgreSQL container name accordingly
if [ "$CODESPACES" == "true" ]; then
    echo -e "${BLUE}Detected GitHub Codespaces environment...${NC}"
    ENV="codespace"
    POSTGRES_CONTAINER="postgres17-pgvector-codespace"
elif grep -qi microsoft /proc/version 2>/dev/null; then
    echo -e "${BLUE}Detected WSL environment...${NC}"
    ENV="wsl"
    POSTGRES_CONTAINER="postgres17-pgvector-wsl"
else
    # Default container name for other environments
    ENV="development"
    POSTGRES_CONTAINER="proethica-postgres"
fi

echo -e "${BLUE}Using environment: ${ENV} with container: ${POSTGRES_CONTAINER}${NC}"

# Check if Docker is installed and running
echo -e "${BLUE}Checking Docker and PostgreSQL container...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed or not in PATH. Database may not work correctly.${NC}"
else
    # Check if PostgreSQL container is running
    CONTAINER_STATUS=$(docker ps -a --filter "name=$POSTGRES_CONTAINER" --format "{{.Status}}")
    
    if [ -z "$CONTAINER_STATUS" ]; then
        echo -e "${YELLOW}PostgreSQL container '$POSTGRES_CONTAINER' not found. Starting with docker-compose...${NC}"
        docker-compose up -d postgres
        echo -e "${YELLOW}Waiting for database to initialize...${NC}"
        sleep 10
    else
        if [[ $CONTAINER_STATUS == Exited* ]] || [[ $CONTAINER_STATUS == Created* ]]; then
            echo -e "${YELLOW}PostgreSQL container '$POSTGRES_CONTAINER' exists but is not running. Starting it now...${NC}"
            if docker start $POSTGRES_CONTAINER; then
                echo -e "${GREEN}PostgreSQL container started successfully.${NC}"
                # Wait for PostgreSQL to initialize
                echo -e "${YELLOW}Waiting for PostgreSQL to initialize...${NC}"
                sleep 5
            else
                echo -e "${RED}Failed to start PostgreSQL container. Please check Docker logs.${NC}"
            fi
        else
            echo -e "${GREEN}PostgreSQL container '$POSTGRES_CONTAINER' is already running.${NC}"
        fi
    fi
    
    # Verify database connectivity
    echo -e "${YELLOW}Verifying database connectivity...${NC}"
    if docker exec $POSTGRES_CONTAINER pg_isready -U postgres -h localhost; then
        echo -e "${GREEN}Database connection verified successfully.${NC}"
    else
        echo -e "${RED}Could not connect to database. Please check container logs:${NC}"
        docker logs --tail 20 $POSTGRES_CONTAINER
    fi
fi

echo -e "${BLUE}=================================================${NC}"
echo -e "${YELLOW}To run the servers with mock guideline responses:${NC}"
echo -e "${BLUE}=================================================${NC}"
echo -e "${GREEN}1. In the first terminal, run the MCP server:${NC}"
echo -e "   export USE_MOCK_GUIDELINE_RESPONSES=true"
echo -e "   python mcp/run_enhanced_mcp_server_with_guidelines.py --port 5001"
echo -e ""
echo -e "${GREEN}2. In a second terminal, run the Flask app:${NC}"
echo -e "   export USE_MOCK_GUIDELINE_RESPONSES=true"
echo -e "   ./debug_app.sh"
echo -e ""
echo -e "${YELLOW}The environment variable has been set in this terminal.${NC}"
echo -e "${YELLOW}You can now run either the MCP server or Flask app from here.${NC}"
echo -e "${BLUE}=================================================${NC}"

# Ask if user wants to run MCP server directly from this script
read -p "Would you like to start the MCP server now? (y/n): " start_mcp
if [[ $start_mcp == "y" || $start_mcp == "Y" ]]; then
    echo -e "${BLUE}Starting MCP server with mock guideline responses...${NC}"
    # Set environment variable to indicate that MCP server is already running
    export MCP_SERVER_ALREADY_RUNNING=true
    python mcp/run_enhanced_mcp_server_with_guidelines.py --port 5001
else
    echo -e "${YELLOW}Remember to manually start both servers with USE_MOCK_GUIDELINE_RESPONSES=true${NC}"
fi
