#!/bin/bash
# run_with_enhanced_mcp.sh
#
# Start the main application without starting another MCP server

set -e  # Exit on error

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== ProEthica with Enhanced MCP Launcher ===${NC}"
echo -e "${GREEN}Starting ProEthica with existing Enhanced MCP server...${NC}"

# Set environment variable to skip MCP server startup in run.py
export SKIP_MCP_SERVER=true
export MCP_SERVER_URL=http://localhost:5001

# Check if run_with_env.sh exists
if [ -f "./scripts/run_with_env.sh" ] && [ -x "./scripts/run_with_env.sh" ]; then
    echo -e "${GREEN}Using run_with_env.sh for proper environment variable handling${NC}"
    ./scripts/run_with_env.sh python run.py
else
    echo -e "${YELLOW}Running directly without run_with_env.sh${NC}"
    python run.py
fi
