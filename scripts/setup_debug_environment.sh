#!/bin/bash
#
# Setup script for VSCode debugging that prepares the environment
# without actually launching the application (that will be done by the debugger)

set -e  # Exit on error

# Source the Python path setup script
if [ -f "./scripts/ensure_python_path.sh" ]; then
    echo "Setting up Python environment paths..."
    source ./scripts/ensure_python_path.sh
else
    echo "Warning: Python path setup script not found"
fi

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== ProEthica Debug Environment Setup ===${NC}"
echo -e "${YELLOW}Preparing environment for debugging...${NC}"

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

# Apply fixes to MCP client and Claude model references if needed
echo -e "${BLUE}Applying MCP client and model reference fixes...${NC}"
if [ -f "./fix_mcp_client.py" ]; then
    echo -e "${YELLOW}Updating MCP client to use JSON-RPC API...${NC}"
    python fix_mcp_client.py
fi

if [ -f "./update_claude_models_in_mcp_server.py" ]; then
    echo -e "${YELLOW}Updating Claude model references...${NC}"
    python update_claude_models_in_mcp_server.py
fi

# Check if port 5001 is already in use and kill the process if needed
echo -e "${BLUE}Checking if port 5001 is already in use...${NC}"
if netstat -tuln 2>/dev/null | grep -q ":5001 "; then
    echo -e "${YELLOW}Port 5001 is already in use. Attempting to find and kill the process...${NC}"
    if command -v fuser >/dev/null 2>&1; then
        fuser -k 5001/tcp >/dev/null 2>&1 || true
        echo -e "${GREEN}Process using port 5001 has been terminated.${NC}"
    else
        echo -e "${YELLOW}fuser command not available. Please manually ensure port 5001 is free.${NC}"
    fi
    sleep 2
else
    echo -e "${GREEN}Port 5001 is available.${NC}"
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

# Set environment variable to indicate that MCP server is already running for other scripts
export MCP_SERVER_ALREADY_RUNNING=true
echo -e "${BLUE}Setting MCP_SERVER_ALREADY_RUNNING=true to prevent starting duplicate MCP server${NC}"

echo -e "${GREEN}Environment setup for debugging complete!${NC}"
echo -e "${YELLOW}You can now run the debugger in VSCode.${NC}"
