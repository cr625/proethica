#!/bin/bash
# Unified debugging script that runs both the MCP server and Flask app
# with mock guideline responses enabled

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}====================================================${NC}"
echo -e "${YELLOW}UNIFIED DEBUG WITH MOCK GUIDELINE RESPONSES${NC}"
echo -e "${BLUE}====================================================${NC}"

# Enable mock guideline responses
export USE_MOCK_GUIDELINE_RESPONSES=true
echo -e "${GREEN}Enabled mock guideline responses${NC}"

# Kill any existing MCP server and Flask app processes
echo -e "${BLUE}Checking for existing processes...${NC}"
pkill -f "python mcp/run_enhanced_mcp_server_with_guidelines.py" 2>/dev/null
pkill -f "flask run --port 3333" 2>/dev/null
sleep 1

# Ensure the PostgreSQL container is running
echo -e "${BLUE}Checking PostgreSQL container...${NC}"

# Detect environment and set PostgreSQL container name accordingly
if [ "$CODESPACES" == "true" ]; then
    echo -e "${BLUE}Detected GitHub Codespaces environment...${NC}"
    ENV="codespace"
    POSTGRES_CONTAINER="postgres17-pgvector-codespace"
    
    # Check if setup script exists and run it
    if [ -f "./scripts/setup_codespace_db.sh" ]; then
        if [ ! -x "./scripts/setup_codespace_db.sh" ]; then
            echo -e "${YELLOW}Making setup_codespace_db.sh executable...${NC}"
            chmod +x ./scripts/setup_codespace_db.sh
        fi
        
        # Run the codespace setup script
        echo -e "${BLUE}Setting up PostgreSQL for codespace environment...${NC}"
        ./scripts/setup_codespace_db.sh
    else
        echo -e "${RED}Codespace setup script not found. Database may not work correctly.${NC}"
    fi
elif grep -qi microsoft /proc/version 2>/dev/null; then
    echo -e "${BLUE}Detected WSL environment...${NC}"
    ENV="wsl"
    POSTGRES_CONTAINER="postgres17-pgvector-wsl"
    
    # Check if native PostgreSQL is running and stop it if needed
    if command -v service &> /dev/null && service postgresql status &> /dev/null; then
        echo -e "${YELLOW}Native PostgreSQL is running in WSL. Stopping it to avoid port conflicts...${NC}"
        sudo service postgresql stop || echo -e "${RED}Could not stop PostgreSQL service. You may experience port conflicts.${NC}"
    fi
else
    # Default container name for other environments
    ENV="development"
    POSTGRES_CONTAINER="postgres17-pgvector"
fi

echo -e "${BLUE}Using environment: ${ENV} with container: ${POSTGRES_CONTAINER}${NC}"

# Extract database connection details from .env file if it exists
DB_PORT="5433"  # Default port
if [ -f ".env" ] && grep -q "DATABASE_URL" .env; then
    EXTRACTED_PORT=$(grep "DATABASE_URL" .env | sed -E 's/.*localhost:([0-9]+).*/\1/')
    if [ ! -z "$EXTRACTED_PORT" ]; then
        DB_PORT=$EXTRACTED_PORT
    fi
fi

# Check Docker if not in Codespaces (Codespaces has its own Docker handling in the setup script)
if [ "$CODESPACES" != "true" ]; then
    # Check if Docker is installed and running
    if ! command -v docker &> /dev/null; then
        echo -e "${YELLOW}Docker is not installed or not in PATH. Skipping Docker checks.${NC}"
    else
        # Check container status
        CONTAINER_STATUS=$(docker ps -a --filter "name=$POSTGRES_CONTAINER" --format "{{.Status}}")
        
        if [ -z "$CONTAINER_STATUS" ]; then
            echo -e "${YELLOW}PostgreSQL container '$POSTGRES_CONTAINER' not found.${NC}"
            echo -e "${YELLOW}Setting up shared PostgreSQL container...${NC}"
            
            # Check if shared postgres setup script exists
            if [ -f "./scripts/setup_shared_postgres.sh" ]; then
                chmod +x ./scripts/setup_shared_postgres.sh
                ./scripts/setup_shared_postgres.sh
            else
                echo -e "${YELLOW}Setup script not found. Using docker-compose to start postgres...${NC}"
                docker-compose up -d postgres
            fi
            
            echo -e "${YELLOW}Waiting for database to initialize...${NC}"
            sleep 10
        else
            if [[ $CONTAINER_STATUS == Exited* ]] || [[ $CONTAINER_STATUS == Created* ]]; then
                echo -e "${YELLOW}PostgreSQL container '$POSTGRES_CONTAINER' exists but is not running. Starting it now...${NC}"
                if docker start $POSTGRES_CONTAINER; then
                    echo -e "${GREEN}PostgreSQL container started successfully on port $DB_PORT.${NC}"
                    echo -e "${YELLOW}Waiting for PostgreSQL to initialize...${NC}"
                    sleep 5
                else
                    echo -e "${RED}Failed to start PostgreSQL container. Please check Docker logs.${NC}"
                fi
            else
                echo -e "${GREEN}PostgreSQL container '$POSTGRES_CONTAINER' is already running on port $DB_PORT.${NC}"
            fi
        fi
    fi
fi

# Apply SQLAlchemy URL fix if needed
echo -e "${BLUE}Applying SQLAlchemy URL fix...${NC}"
./patch_sqlalchemy_url.py app/__init__.py

# Start the MCP server in the background
echo -e "${BLUE}Starting MCP server with mock guideline responses...${NC}"
python mcp/run_enhanced_mcp_server_with_guidelines.py --port 5001 > mcp_server_log.txt 2>&1 &
MCP_PID=$!

echo -e "${YELLOW}MCP server starting with PID: $MCP_PID${NC}"

# Wait for MCP server to initialize
echo -e "${YELLOW}Waiting for MCP server to initialize...${NC}"
sleep 5

# Check if MCP server is running
if ps -p $MCP_PID > /dev/null; then
    echo -e "${GREEN}MCP server is running.${NC}"
else
    echo -e "${RED}MCP server failed to start. Check mcp_server_log.txt for details.${NC}"
    exit 1
fi

# Test MCP server connectivity
echo -e "${BLUE}Testing connection to MCP server at http://localhost:5001...${NC}"
curl -s -o /dev/null -w "%{http_code}" http://localhost:5001/status > /dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}MCP server is responding.${NC}"
else
    echo -e "${YELLOW}Warning: Could not verify MCP server status. Continuing anyway...${NC}"
fi

# Set debug environment variables
export FLASK_ENV=development
export FLASK_DEBUG=1
export MCP_DEBUG=true

echo -e "${BLUE}====================================================${NC}"
echo -e "${YELLOW}DEBUG ENVIRONMENT READY${NC}"
echo -e "${BLUE}====================================================${NC}"
echo -e "${GREEN}MCP Server: Running with mock responses (PID: $MCP_PID)${NC}"
echo -e "${GREEN}MCP Server Log: mcp_server_log.txt${NC}"
echo -e "${GREEN}To debug:${NC}"
echo -e "  1. Set breakpoints in VSCode"
echo -e "  2. In VSCode Run panel, select 'Python: Flask' from dropdown"
echo -e "  3. Click start debugging (F5)"
echo -e ""
echo -e "${YELLOW}Or run the Flask app directly:${NC}"
echo -e "  ./debug_app.sh"
echo -e ""
echo -e "${RED}To stop everything when done:${NC}"
echo -e "  kill $MCP_PID"
echo -e "${BLUE}====================================================${NC}"

# Option to start the Flask app directly
read -p "Start Flask app now? (y/n): " start_flask
if [[ $start_flask == "y" || $start_flask == "Y" ]]; then
    echo -e "${BLUE}Starting Flask app...${NC}"
    ./debug_app.sh
else
    echo -e "${YELLOW}Start the Flask app manually or use VSCode debugger.${NC}"
    echo -e "${YELLOW}MCP server is running in the background.${NC}"
fi
