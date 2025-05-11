#!/bin/bash
# Script to stop the Unified Ontology MCP Server

# Set colored output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Stopping Unified Ontology MCP Server...${NC}"

# Check if PID file exists
if [ -f "unified_ontology_server.pid" ]; then
    SERVER_PID=$(cat unified_ontology_server.pid)
    
    # Check if the process is still running
    if ps -p $SERVER_PID > /dev/null; then
        echo -e "${BLUE}Sending graceful shutdown signal to PID ${SERVER_PID}...${NC}"
        kill $SERVER_PID
        
        # Wait for the process to terminate
        for i in {1..5}; do
            if ! ps -p $SERVER_PID > /dev/null; then
                echo -e "${GREEN}Server shutdown successfully!${NC}"
                rm unified_ontology_server.pid
                exit 0
            fi
            echo -e "${YELLOW}Waiting for server to shut down (attempt $i/5)...${NC}"
            sleep 1
        done
        
        # Force kill if still running
        echo -e "${YELLOW}Server still running. Sending SIGKILL...${NC}"
        kill -9 $SERVER_PID || true
        sleep 1
        
        if ! ps -p $SERVER_PID > /dev/null; then
            echo -e "${GREEN}Server forcibly terminated.${NC}"
        else
            echo -e "${RED}Failed to terminate server process.${NC}"
        fi
    else
        echo -e "${YELLOW}Server process ${SERVER_PID} is not running.${NC}"
    fi
    
    # Clean up PID file
    rm unified_ontology_server.pid
else
    # Try to find and kill by pattern matching
    echo -e "${YELLOW}PID file not found. Attempting to find server process...${NC}"
    
    PIDS=$(pgrep -f "python3 run_unified_mcp_server.py" || true)
    
    if [ -z "$PIDS" ]; then
        echo -e "${YELLOW}No running server processes found.${NC}"
    else
        echo -e "${BLUE}Found server processes: ${PIDS}${NC}"
        
        for PID in $PIDS; do
            echo -e "${BLUE}Killing process ${PID}...${NC}"
            kill $PID || true
        done
        
        sleep 1
        
        # Check if processes are still running
        REMAINING=$(pgrep -f "python3 run_unified_mcp_server.py" || true)
        
        if [ -z "$REMAINING" ]; then
            echo -e "${GREEN}All server processes terminated.${NC}"
        else
            echo -e "${YELLOW}Some processes still running. Sending SIGKILL...${NC}"
            for PID in $REMAINING; do
                kill -9 $PID || true
            done
            
            sleep 1
            
            if pgrep -f "python3 run_unified_mcp_server.py" > /dev/null; then
                echo -e "${RED}Failed to terminate all server processes.${NC}"
            else
                echo -e "${GREEN}All server processes forcibly terminated.${NC}"
            fi
        fi
    fi
fi

echo -e "${BLUE}Cleanup completed.${NC}"
