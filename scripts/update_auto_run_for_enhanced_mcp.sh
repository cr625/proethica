#!/bin/bash
# update_auto_run_for_enhanced_mcp.sh
#
# This script updates auto_run.sh to use the enhanced MCP server instead of the standard HTTP MCP server

set -e  # Exit on error

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Updating auto_run.sh for Enhanced MCP Server ===${NC}"

# Create backup of auto_run.sh
BACKUP_FILE="auto_run.sh.bak.$(date +%Y%m%d%H%M%S)"
cp auto_run.sh $BACKUP_FILE
echo -e "${GREEN}Created backup of auto_run.sh at $BACKUP_FILE${NC}"

# Update auto_run.sh to use enhanced MCP server
sed -i 's|./scripts/restart_http_mcp_server.sh|./scripts/restart_mcp_server.sh|g' auto_run.sh

# Make sure the restart_mcp_server.sh script is executable
chmod +x scripts/restart_mcp_server.sh

echo -e "${GREEN}Updated auto_run.sh to use enhanced MCP server${NC}"
echo -e "${YELLOW}You can now run ./start_proethica.sh to start the application with enhanced MCP server${NC}"
