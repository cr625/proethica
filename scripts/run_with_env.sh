#!/bin/bash
# run_with_env.sh
#
# Utility script to run Python commands with proper environment variables
# loaded from the .env file. This solves the Claude API authentication issues
# by properly exporting all variables to the process environment.

set -e  # Exit on error

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Environment Variable Loader ===${NC}"

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}ERROR: No .env file found in the current directory!${NC}"
    echo -e "${YELLOW}This script must be run from the ProEthica root directory.${NC}"
    exit 1
fi

# Export all environment variables from .env file (excluding comments)
echo -e "${YELLOW}Exporting environment variables from .env file...${NC}"
export $(grep -v '^#' .env | xargs)

# Run the command provided as arguments
if [ $# -eq 0 ]; then
    echo -e "${RED}ERROR: No command specified!${NC}"
    echo -e "${YELLOW}Usage: ./scripts/run_with_env.sh <command>${NC}"
    echo -e "${YELLOW}Example: ./scripts/run_with_env.sh python scripts/check_claude_api.py${NC}"
    exit 1
else
    echo -e "${GREEN}Running command with exported environment: $@${NC}"
    "$@"
fi
