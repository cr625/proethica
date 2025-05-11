#!/bin/bash

# Script to start the unified ontology MCP server

# Color definitions
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Environment setup
PORT=${MCP_SERVER_PORT:-5002}
HOST="0.0.0.0"

echo -e "${BLUE}Starting Unified Ontology MCP Server on ${YELLOW}${HOST}:${PORT}${NC}"

# Check if the server is already running
PID=$(pgrep -f "python.*run_unified_mcp_server.py")
if [ ! -z "$PID" ]; then
    echo -e "${YELLOW}Warning: Unified Ontology MCP Server is already running (PID: $PID)${NC}"
    read -p "Do you want to stop it and start a new instance? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Stopping existing server...${NC}"
        kill $PID
        sleep 2
    else
        echo -e "${YELLOW}Exiting without starting a new server.${NC}"
        exit 0
    fi
fi

# Set up Python environment
if [ -d "venv" ]; then
    echo -e "${BLUE}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Load environment variables
if [ -f .env ]; then
    echo -e "${BLUE}Loading environment variables from .env file...${NC}"
    export $(grep -v '^#' .env | xargs)
fi

# Make sure the unified MCP server script is executable
chmod +x run_unified_mcp_server.py

# Start the server
echo -e "${BLUE}Starting unified ontology MCP server...${NC}"

LOGFILE="logs/unified_ontology_server_$(date +%Y%m%d_%H%M%S).log"
mkdir -p logs

# Create the command to run
CMD="python run_unified_mcp_server.py --host $HOST --port $PORT"

# Start the server in the background with nohup
nohup $CMD > "$LOGFILE" 2>&1 &

# Get the PID of the process
SERVER_PID=$!

# Check if the server started successfully
sleep 2
if ps -p $SERVER_PID > /dev/null; then
    echo -e "${GREEN}Server started successfully with PID ${YELLOW}${SERVER_PID}${NC}"
    echo -e "${BLUE}Logs are being written to ${YELLOW}${LOGFILE}${NC}"
    echo -e "${BLUE}Server is running at ${YELLOW}http://${HOST}:${PORT}${NC}"
    echo -e "${BLUE}Use ${YELLOW}stop_unified_ontology_server.sh${BLUE} to stop the server${NC}"
else
    echo -e "${RED}Failed to start the server. Check the logs: ${YELLOW}${LOGFILE}${NC}"
    tail -n 10 "$LOGFILE"
    exit 1
fi
