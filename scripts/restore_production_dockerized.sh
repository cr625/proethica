#!/bin/bash
# Script to restore the production environment with Docker PostgreSQL and enhanced MCP server
# Created on: 2025-04-29

set -e  # Exit on error

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== ProEthica Production Environment Restoration ===${NC}"

# Check if script is run as root
if [ "$(id -u)" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root${NC}"
    echo -e "Please run: sudo $0"
    exit 1
fi

# Working directory
WORKING_DIR="/var/www/proethica"
cd "$WORKING_DIR" || { echo -e "${RED}Error: Cannot change to $WORKING_DIR${NC}"; exit 1; }

echo -e "${YELLOW}Stopping all services...${NC}"
systemctl stop proethica.service mcp-server.service proethica-postgres.service || true

echo -e "${YELLOW}Ensuring Docker is running...${NC}"
systemctl start docker || { echo -e "${RED}Error: Failed to start Docker${NC}"; exit 1; }

echo -e "${BLUE}Copying service files to /etc/systemd/system...${NC}"
cp -v server_config/proethica-postgres.service /etc/systemd/system/
cp -v server_config/mcp-server.service /etc/systemd/system/
cp -v server_config/proethica.service /etc/systemd/system/

echo -e "${BLUE}Reloading systemd...${NC}"
systemctl daemon-reload

echo -e "${YELLOW}Starting Docker PostgreSQL container...${NC}"
systemctl start proethica-postgres.service
sleep 2

echo -e "${BLUE}Checking Docker container status...${NC}"
docker ps | grep proethica-postgres || { 
    echo -e "${RED}Error: PostgreSQL container not running${NC}"
    echo -e "Check logs: journalctl -u proethica-postgres.service"
    exit 1
}

echo -e "${YELLOW}Initializing git submodule...${NC}"
git submodule update --init --recursive

echo -e "${YELLOW}Starting MCP server with enhanced ontology support...${NC}"
systemctl start mcp-server.service
sleep 2

echo -e "${BLUE}Checking MCP server status...${NC}"
systemctl status mcp-server.service --no-pager || {
    echo -e "${RED}Error: MCP server not running${NC}"
    echo -e "Check logs: journalctl -u mcp-server.service"
    exit 1
}

echo -e "${YELLOW}Starting ProEthica application...${NC}"
systemctl start proethica.service
sleep 2

echo -e "${BLUE}Checking ProEthica application status...${NC}"
systemctl status proethica.service --no-pager || {
    echo -e "${RED}Error: ProEthica application not running${NC}"
    echo -e "Check logs: journalctl -u proethica.service"
    exit 1
}

echo -e "${GREEN}Success! Production environment has been restored with:${NC}"
echo -e "  - Docker PostgreSQL with pgvector"
echo -e "  - Enhanced MCP server"
echo -e "  - ProEthica application"
echo ""
echo -e "${YELLOW}Services status:${NC}"
echo -e "  PostgreSQL: $(systemctl is-active proethica-postgres.service)"
echo -e "  MCP Server: $(systemctl is-active mcp-server.service)"
echo -e "  ProEthica: $(systemctl is-active proethica.service)"
echo ""
echo -e "${BLUE}Access the application at: http://localhost:5000${NC}"
