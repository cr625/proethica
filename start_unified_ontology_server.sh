#!/bin/bash
# Script to start the Unified Ontology MCP Server

# Set colored output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if we're in the right directory
if [ ! -f "run_unified_mcp_server.py" ]; then
    echo -e "${RED}Error: run_unified_mcp_server.py not found in current directory.${NC}"
    echo -e "${YELLOW}Please run this script from the project root directory.${NC}"
    exit 1
fi

# Make sure run_unified_mcp_server.py is executable
chmod +x run_unified_mcp_server.py

# Set up the Python environment
echo -e "${BLUE}Setting up Python environment...${NC}"

# Check if virtual environment exists
if [ -d "venv" ] || [ -d ".venv" ]; then
    # Activate virtual environment if it exists
    if [ -d "venv" ]; then
        echo -e "${GREEN}Activating virtual environment: venv${NC}"
        source venv/bin/activate
    else
        echo -e "${GREEN}Activating virtual environment: .venv${NC}"
        source .venv/bin/activate
    fi
else
    echo -e "${YELLOW}No virtual environment found. Using system Python.${NC}"
fi

# Set environment variables
export FLASK_APP=app
export FLASK_ENV=development
export PYTHONPATH=$PYTHONPATH:$(pwd)

# Clean up any previous instances
echo -e "${BLUE}Checking for previous server instances...${NC}"
pkill -f "python3 run_unified_mcp_server.py" || true
sleep 1

# Start the server
echo -e "${BLUE}Starting Unified Ontology MCP Server...${NC}"
echo -e "${YELLOW}Server will be available at: http://localhost:5001${NC}"
echo -e "${YELLOW}API documentation available at: http://localhost:5001/info${NC}"

# Run in the background with output to log file
echo -e "${BLUE}Running server in the background. Logs will be written to unified_ontology_server.log${NC}"
python3 run_unified_mcp_server.py > unified_ontology_server.log 2>&1 &

# Store the PID
SERVER_PID=$!
echo $SERVER_PID > unified_ontology_server.pid
echo -e "${GREEN}Server started with PID: ${SERVER_PID}${NC}"

# Wait a bit for the server to start
sleep 2

# Check if the server is running
if ps -p $SERVER_PID > /dev/null; then
    echo -e "${GREEN}Server is running successfully!${NC}"
    echo -e "${YELLOW}===========================================${NC}"
    echo -e "${YELLOW}Available modules and tools:${NC}"
    curl -s http://localhost:5001/info | python3 -m json.tool
    echo -e "${YELLOW}===========================================${NC}"
    echo -e "${YELLOW}To stop the server: ./stop_unified_ontology_server.sh${NC}"
    echo -e "${YELLOW}To view logs: cat unified_ontology_server.log${NC}"
    echo -e "${YELLOW}To tail logs: tail -f unified_ontology_server.log${NC}"
else
    echo -e "${RED}Server failed to start. Check logs: unified_ontology_server.log${NC}"
    exit 1
fi
