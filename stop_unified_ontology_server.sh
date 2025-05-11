#!/bin/bash

# Script to stop the unified ontology MCP server

# Color definitions
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Looking for Unified Ontology MCP Server processes...${NC}"

# Find the process running the unified ontology MCP server
PID=$(pgrep -f "python.*run_unified_mcp_server.py")

if [ -z "$PID" ]; then
    echo -e "${YELLOW}No Unified Ontology MCP Server process found.${NC}"
    exit 0
else
    echo -e "${BLUE}Found Unified Ontology MCP Server running with PID ${YELLOW}${PID}${NC}"
    
    # Ask for confirmation
    read -p "Do you want to stop this server? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Stopping server...${NC}"
        
        # Try to gracefully terminate the process
        kill $PID
        
        # Wait for a moment to see if it terminated
        sleep 2
        
        # Check if the process is still running
        if ps -p $PID > /dev/null; then
            echo -e "${YELLOW}Process is still running. Forcing termination...${NC}"
            kill -9 $PID
            sleep 1
        fi
        
        # Final check
        if ps -p $PID > /dev/null; then
            echo -e "${RED}Failed to stop the server (PID: $PID).${NC}"
            exit 1
        else
            echo -e "${GREEN}Server stopped successfully.${NC}"
        fi
    else
        echo -e "${YELLOW}Operation cancelled.${NC}"
    fi
fi

# Optionally clean up any zombie Python processes related to the server
ZOMBIE_PIDS=$(pgrep -f "python.*unified_ontology_server" | grep -v "$PID")
if [ ! -z "$ZOMBIE_PIDS" ]; then
    echo -e "${YELLOW}Found additional related processes: ${ZOMBIE_PIDS}${NC}"
    read -p "Do you want to clean up these processes too? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Cleaning up additional processes...${NC}"
        kill $ZOMBIE_PIDS 2>/dev/null || kill -9 $ZOMBIE_PIDS 2>/dev/null
        echo -e "${GREEN}Cleanup complete.${NC}"
    fi
fi

# Print summary
echo -e "${GREEN}Unified Ontology MCP Server has been stopped.${NC}"
echo -e "${BLUE}You can restart it using ${YELLOW}start_unified_ontology_server.sh${NC}"
