#!/bin/bash
#
# ProEthica Codespace Launcher
# This script automates the proper startup of ProEthica in the GitHub Codespaces environment,
# applying all necessary fixes for the database and MCP server.

set -e  # Exit on error

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== ProEthica Codespace Launcher ===${NC}"

# Fix database password
echo -e "${YELLOW}Fixing database connection...${NC}"
python fix_db_password.py

# Start JSON fixer proxy in the background
echo -e "${YELLOW}Starting MCP JSON fixer proxy...${NC}"
python mcp_json_fixer.py > logs/mcp_json_fixer.log 2>&1 &
FIXER_PID=$!
echo -e "${GREEN}MCP JSON fixer proxy started with PID ${FIXER_PID}${NC}"

# Wait for JSON fixer to initialize
sleep 2

# Update MCP_SERVER_URL in .env file to point to JSON fixer proxy
echo -e "${YELLOW}Updating MCP server URL to use JSON fixer proxy...${NC}"
if [ -f ".env" ]; then
    sed -i 's|MCP_SERVER_URL=http://localhost:5001|MCP_SERVER_URL=http://localhost:5002|g' .env
    echo -e "${GREEN}Updated .env file to use JSON fixer proxy${NC}"
else
    echo -e "${RED}Error: .env file not found${NC}"
    exit 1
fi

# Run the unified ProEthica launcher
echo -e "${BLUE}Starting ProEthica with restored UI...${NC}"
python run_proethica_unified.py

# Clean up background processes
cleanup() {
    echo -e "${YELLOW}Cleaning up background processes...${NC}"
    if ps -p $FIXER_PID > /dev/null; then
        kill $FIXER_PID
        echo -e "${GREEN}Stopped JSON fixer proxy (PID: $FIXER_PID)${NC}"
    fi
}

# Register the cleanup function to be called on script exit
trap cleanup EXIT
