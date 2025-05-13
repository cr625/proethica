#!/bin/bash
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

echo -e "${BLUE}=== ProEthica Starter with Guidelines Support ===${NC}"
echo -e "${YELLOW}Starting ProEthica with environment auto-detection...${NC}"

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

# Environment detection
if [ "$CODESPACES" == "true" ]; then
    echo -e "${BLUE}Detected GitHub Codespaces environment...${NC}"
    ENV="codespace"
    POSTGRES_CONTAINER="postgres17-pgvector-codespace"

    # Check if setup script exists and is executable
    if [ -f "./scripts/setup_codespace_db.sh" ]; then
        if [ ! -x "./scripts/setup_codespace_db.sh" ]; then
            echo -e "${YELLOW}Making setup_codespace_db.sh executable...${NC}"
            chmod +x ./scripts/setup_codespace_db.sh
        fi

        # Run the codespace setup script
        echo -e "${BLUE}Setting up PostgreSQL for codespace environment...${NC}"
        ./scripts/setup_codespace_db.sh
        
        # Check if we have our password fix script and run it
        if [ -f "./fix_db_password.sh" ]; then
            if [ ! -x "./fix_db_password.sh" ]; then
                echo -e "${YELLOW}Making fix_db_password.sh executable...${NC}"
                chmod +x ./fix_db_password.sh
            fi
            echo -e "${BLUE}Setting PostgreSQL password to match .env configuration...${NC}"
            ./fix_db_password.sh
        fi
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

# Check if .env exists and ensure it has necessary settings
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}No .env file found. Creating one from .env.example...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}Adding MCP_SERVER_URL and other settings to .env file...${NC}"
    echo "MCP_SERVER_URL=http://localhost:5001" >> .env
    echo "USE_MOCK_FALLBACK=false" >> .env
    echo "CLAUDE_MODEL_VERSION=claude-3-7-sonnet-20250219" >> .env
    echo "SET_CSRF_TOKEN_ON_PAGE_LOAD=true" >> .env
else
    # Update existing .env file with correct settings
    # If in Codespaces, ensure DATABASE_URL is updated with the correct password
    if [ "$CODESPACES" == "true" ]; then
        echo -e "${YELLOW}Updating DATABASE_URL for Codespaces environment...${NC}"
        # Use 'PASS' as the password for Codespaces environment
        sed -i "s|DATABASE_URL=.*|DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm|g" .env
    fi
    
    if ! grep -q "MCP_SERVER_URL=" .env; then
        echo -e "${YELLOW}Adding MCP_SERVER_URL to .env file...${NC}"
        echo "MCP_SERVER_URL=http://localhost:5001" >> .env
    else
        # Update existing MCP_SERVER_URL to use port 5001
        sed -i "s|MCP_SERVER_URL=http://localhost:[0-9]*|MCP_SERVER_URL=http://localhost:5001|g" .env
    fi

    if ! grep -q "USE_MOCK_FALLBACK=" .env; then
        echo -e "${YELLOW}Adding USE_MOCK_FALLBACK to .env file...${NC}"
        echo "USE_MOCK_FALLBACK=false" >> .env
    else
        # Do not override existing value
        echo -e "${BLUE}Using existing USE_MOCK_FALLBACK setting from .env file${NC}"
    fi
    
    if ! grep -q "CLAUDE_MODEL_VERSION=" .env; then
        echo -e "${YELLOW}Adding CLAUDE_MODEL_VERSION to .env file...${NC}"
        echo "CLAUDE_MODEL_VERSION=claude-3-7-sonnet-20250219" >> .env
    else
        # Update Claude model version to the latest
        sed -i "s|CLAUDE_MODEL_VERSION=.*|CLAUDE_MODEL_VERSION=claude-3-7-sonnet-20250219|g" .env
    fi
    
    if ! grep -q "SET_CSRF_TOKEN_ON_PAGE_LOAD=" .env; then
        echo -e "${YELLOW}Adding SET_CSRF_TOKEN_ON_PAGE_LOAD to .env file...${NC}"
        echo "SET_CSRF_TOKEN_ON_PAGE_LOAD=true" >> .env
    fi
fi

# Clean up any existing MCP server processes
echo -e "${BLUE}Checking for running MCP server processes...${NC}"
if pgrep -f "run_enhanced_mcp_server.py" > /dev/null || pgrep -f "enhanced_ontology_server_with_guidelines.py" > /dev/null || pgrep -f "http_ontology_mcp_server.py" > /dev/null || pgrep -f "run_unified_mcp_server.py" > /dev/null; then
    echo -e "${YELLOW}Stopping existing MCP server processes...${NC}"
    pkill -f "run_enhanced_mcp_server.py" 2>/dev/null || true
    pkill -f "run_enhanced_mcp_server_with_guidelines.py" 2>/dev/null || true
    pkill -f "http_ontology_mcp_server.py" 2>/dev/null || true
    pkill -f "ontology_mcp_server.py" 2>/dev/null || true
    pkill -f "run_unified_mcp_server.py" 2>/dev/null || true
    sleep 2
fi

# Check Docker if not in Codespaces (Codespaces has its own Docker handling in the setup script)
if [ "$CODESPACES" != "true" ]; then
    # Check if Docker is installed and running
    echo -e "${BLUE}Checking Docker and PostgreSQL container...${NC}"
    if ! command -v docker &> /dev/null; then
        echo -e "${YELLOW}Docker is not installed or not in PATH. Skipping Docker checks.${NC}"
    else
        # Extract database connection details from .env file
        DB_PORT=$(grep "DATABASE_URL" .env | sed -E 's/.*localhost:([0-9]+).*/\1/')

        if [ -z "$DB_PORT" ]; then
            if [ "$ENV" == "wsl" ]; then
                DB_PORT="5432"  # Default port for WSL
            else
                DB_PORT="5433"  # Default port for other environments
            fi
        fi

        CONTAINER_STATUS=$(docker ps -a --filter "name=$POSTGRES_CONTAINER" --format "{{.Status}}")

        if [ -z "$CONTAINER_STATUS" ]; then
            echo -e "${YELLOW}PostgreSQL container '$POSTGRES_CONTAINER' not found.${NC}"
            echo -e "${YELLOW}Setting up shared PostgreSQL container...${NC}"
            ./scripts/setup_shared_postgres.sh
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
                fi
            else
                echo -e "${GREEN}PostgreSQL container '$POSTGRES_CONTAINER' is already running on port $DB_PORT.${NC}"
            fi
        fi
    fi
fi

# Ensure scripts are executable
chmod +x scripts/restart_mcp_server.sh 2>/dev/null || true
[ -f "./scripts/run_with_env.sh" ] && chmod +x ./scripts/run_with_env.sh 2>/dev/null || true

# Update ENVIRONMENT variable in .env file
if grep -q "^ENVIRONMENT=" .env; then
            # Set environment with proper detection
            if [ "$CODESPACES" == "true" ]; then
                sed -i "s/^ENVIRONMENT=.*/ENVIRONMENT=codespace/" .env
            else
                sed -i "s/^ENVIRONMENT=.*/ENVIRONMENT=$ENV/" .env
            fi
else
    echo "ENVIRONMENT=$ENV" >> .env
fi

# Apply fixes to MCP client and Claude model references
echo -e "${BLUE}Applying MCP client and model reference fixes...${NC}"
if [ -f "./fix_mcp_client.py" ]; then
    echo -e "${YELLOW}Updating MCP client to use JSON-RPC API...${NC}"
    python fix_mcp_client.py
fi

if [ -f "./update_claude_models_in_mcp_server.py" ]; then
    echo -e "${YELLOW}Updating Claude model references...${NC}"
    python update_claude_models_in_mcp_server.py
fi

# Start the enhanced ontology MCP server with guidelines support
echo -e "${BLUE}Starting Enhanced Ontology MCP Server with Guidelines Support...${NC}"

# Environment setup for enhanced ontology server
PORT=${MCP_SERVER_PORT:-5001}
HOST="0.0.0.0"

# Make sure the enhanced MCP server script is executable
if [ -f "./mcp/run_enhanced_mcp_server_with_guidelines.py" ]; then
    chmod +x mcp/run_enhanced_mcp_server_with_guidelines.py
    
    LOGFILE="logs/enhanced_ontology_server_$(date +%Y%m%d_%H%M%S).log"
    mkdir -p logs
    
    # Create the command to run
    CMD="python mcp/run_enhanced_mcp_server_with_guidelines.py"
    
    # Start the server in the background with nohup
    echo -e "${BLUE}Starting enhanced ontology MCP server with guidelines support on ${YELLOW}${HOST}:${PORT}${NC}"
    nohup $CMD > "$LOGFILE" 2>&1 &
    
    # Get the PID of the process
    ENHANCED_SERVER_PID=$!
    
    # Check if the server started successfully
    sleep 2
    if ps -p $ENHANCED_SERVER_PID > /dev/null; then
        echo -e "${GREEN}Enhanced Ontology Server with Guidelines started successfully with PID ${YELLOW}${ENHANCED_SERVER_PID}${NC}"
        echo -e "${BLUE}Logs are being written to ${YELLOW}${LOGFILE}${NC}"
    else
        echo -e "${RED}Failed to start the Enhanced Ontology Server. Check the logs: ${YELLOW}${LOGFILE}${NC}"
        tail -n 10 "$LOGFILE"
    fi
    
    # Test the MCP server connection using the JSON-RPC endpoint
    echo -e "${YELLOW}Testing MCP server JSON-RPC connection...${NC}"
    sleep 3
    
    if [ -f "./test_mcp_jsonrpc_connection.py" ]; then
        if python test_mcp_jsonrpc_connection.py; then
            echo -e "${GREEN}MCP server JSON-RPC connection test successful!${NC}"
        else
            echo -e "${YELLOW}MCP server JSON-RPC connection test failed. Server may not be running correctly.${NC}"
        fi
    else
        # Fallback to curl for testing
        if curl -s -X POST http://localhost:5001/jsonrpc -H "Content-Type: application/json" \
             -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}' | grep -q jsonrpc; then
            echo -e "${GREEN}MCP server JSON-RPC connection test successful!${NC}"
        else
            echo -e "${YELLOW}MCP server JSON-RPC connection test failed. Server may not be running correctly.${NC}"
        fi
    fi
else
    echo -e "${RED}Enhanced ontology server script not found. The guidelines functionality will not be available.${NC}"
    
    # Fall back to unified server if it exists
    if [ -f "./run_unified_mcp_server.py" ]; then
        echo -e "${YELLOW}Falling back to unified ontology server (without guidelines support)...${NC}"
        chmod +x run_unified_mcp_server.py
        
        LOGFILE="logs/unified_ontology_server_$(date +%Y%m%d_%H%M%S).log"
        mkdir -p logs
        
        # Create the command to run
        CMD="python run_unified_mcp_server.py --host $HOST --port $PORT"
        
        # Start the server in the background with nohup
        echo -e "${BLUE}Starting unified ontology MCP server on ${YELLOW}${HOST}:${PORT}${NC}"
        nohup $CMD > "$LOGFILE" 2>&1 &
        
        # Get the PID of the process
        UNIFIED_SERVER_PID=$!
        
        # Check if the server started successfully
        sleep 2
        if ps -p $UNIFIED_SERVER_PID > /dev/null; then
            echo -e "${GREEN}Unified Ontology Server started successfully with PID ${YELLOW}${UNIFIED_SERVER_PID}${NC}"
            echo -e "${BLUE}Logs are being written to ${YELLOW}${LOGFILE}${NC}"
            echo -e "${YELLOW}Note: Guidelines functionality will not be available with the unified server.${NC}"
        else
            echo -e "${RED}Failed to start the Unified Ontology Server. Check the logs: ${YELLOW}${LOGFILE}${NC}"
            tail -n 10 "$LOGFILE"
        fi
    else
        echo -e "${RED}Neither enhanced nor unified ontology server scripts found. Ontology functionality will not be available.${NC}"
    fi
fi

# Initialize database schema if needed
echo -e "${BLUE}Initializing database schema...${NC}"
if [ -f "./scripts/schema_check.py" ]; then
    echo -e "${YELLOW}Checking database schema...${NC}"
    if python ./scripts/schema_check.py; then
        echo -e "${GREEN}Database schema verified successfully. Skipping full initialization.${NC}"
    else
        echo -e "${YELLOW}Schema verification failed. Running full database initialization...${NC}"
        if [ -f "./scripts/initialize_proethica_db.py" ]; then
            python ./scripts/initialize_proethica_db.py
        else
            echo -e "${RED}Database initialization script not found. Some features may not work correctly.${NC}"
        fi
    fi
else
    echo -e "${YELLOW}Schema check script not found. Running full database initialization...${NC}"
    if [ -f "./scripts/initialize_proethica_db.py" ]; then
        python ./scripts/initialize_proethica_db.py
    else
        echo -e "${RED}Database initialization script not found. Some features may not work correctly.${NC}"
    fi
fi

# Launch the application with auto_run.sh
echo -e "${GREEN}Launching ProEthica with auto-detected environment: $ENV${NC}"
# Set environment variable to indicate that MCP server is already running
export MCP_SERVER_ALREADY_RUNNING=true
echo -e "${BLUE}Setting MCP_SERVER_ALREADY_RUNNING=true to prevent starting duplicate MCP server${NC}"
./auto_run.sh

# Register cleanup function for server processes
cleanup() {
    echo -e "${YELLOW}Shutting down MCP server processes...${NC}"
    if [ -n "$ENHANCED_SERVER_PID" ]; then
        kill $ENHANCED_SERVER_PID 2>/dev/null || true
    fi
    if [ -n "$UNIFIED_SERVER_PID" ]; then
        kill $UNIFIED_SERVER_PID 2>/dev/null || true
    fi
    echo -e "${GREEN}Cleanup complete.${NC}"
}

# Register the cleanup function to be called on script exit
trap cleanup EXIT
