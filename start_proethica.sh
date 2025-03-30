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

# Launch the application
echo -e "${GREEN}Launching ProEthica with auto-detected environment...${NC}"
./auto_run.sh
