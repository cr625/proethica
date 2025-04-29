#!/bin/bash
# Environment-aware wrapper for MCP server management
# This script detects the environment and uses the appropriate configuration

# Determine the script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Define colors for output
BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if running in development or production
if [ -f "${SCRIPT_DIR}/../.env" ]; then
    # Source environment variables from .env file if it exists
    # This ensures ENVIRONMENT is set if defined there
    if grep -q "ENVIRONMENT=" "${SCRIPT_DIR}/../.env"; then
        source "${SCRIPT_DIR}/../.env"
        echo -e "${BLUE}Loaded ENVIRONMENT from .env file: ${ENVIRONMENT:-development}${NC}"
    fi
fi

# Set default environment if not already set
if [ -z "$ENVIRONMENT" ]; then
    # Default to development environment
    ENVIRONMENT="development"
    echo -e "${YELLOW}No ENVIRONMENT variable found. Defaulting to: ${ENVIRONMENT}${NC}"
else
    echo -e "${BLUE}Using ENVIRONMENT: ${ENVIRONMENT}${NC}"
fi

# Export the environment variable for the Python script
export ENVIRONMENT

# Ensure the Python script is executable
if [ ! -x "${SCRIPT_DIR}/env_mcp_server.py" ]; then
    echo -e "${YELLOW}Making env_mcp_server.py executable...${NC}"
    chmod +x "${SCRIPT_DIR}/env_mcp_server.py"
fi

# Run the environment-aware Python script
echo -e "${GREEN}Starting MCP server with ${ENVIRONMENT} environment configuration...${NC}"
python3 "${SCRIPT_DIR}/env_mcp_server.py"

# Check the exit status
STATUS=$?
if [ $STATUS -ne 0 ]; then
    echo -e "${RED}Failed to start MCP server. See logs for details.${NC}"
    exit $STATUS
else
    echo -e "${GREEN}MCP server successfully started.${NC}"
    exit 0
fi
