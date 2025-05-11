#!/bin/bash

# Script to restart the unified ontology server properly

# Define colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Restarting Unified Ontology Server...${NC}"

# 1. Stop existing processes
echo "Stopping any existing Unified Ontology Server processes..."
pkill -f "python.*run_unified_mcp_server.py" || true

# Wait a moment to ensure processes are terminated
sleep 2

# 2. Verify the ontology files
echo "Verifying ontology files..."
if [ ! -f "ontologies/bfo.ttl" ] || [ ! -f "ontologies/proethica-intermediate.ttl" ] || [ ! -f "ontologies/engineering-ethics.ttl" ]; then
    echo -e "${RED}Missing required ontology files in the ontologies directory!${NC}"
    exit 1
fi

# 3. Start the unified ontology server
echo "Starting the Unified Ontology Server..."
echo "Server output will be redirected to logs/unified_ontology_server.log"

# Create logs directory if it doesn't exist
mkdir -p logs

# Start the server with nohup to keep it running after the script exits
nohup python run_unified_mcp_server.py --host 0.0.0.0 --port 5001 > logs/unified_ontology_server.log 2>&1 &

# Save the process ID
SERVER_PID=$!

# Wait a moment for the server to start
sleep 3

# 4. Check if the server is running
if ps -p $SERVER_PID > /dev/null; then
    echo -e "${GREEN}Unified Ontology Server started successfully with PID: $SERVER_PID${NC}"
    echo "You can monitor the server output with: tail -f logs/unified_ontology_server.log"
else
    echo -e "${RED}Failed to start Unified Ontology Server!${NC}"
    echo "Check the log file for details: logs/unified_ontology_server.log"
    exit 1
fi

# 5. Test if the server is responding
echo "Testing server connectivity..."
curl -s http://localhost:5001/health > /dev/null
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Server is responding to requests!${NC}"
    curl -s http://localhost:5001/health
else
    echo -e "${RED}Server is not responding to requests!${NC}"
    echo "Check the log file for details: logs/unified_ontology_server.log"
    exit 1
fi

echo -e "${GREEN}Unified Ontology Server restart completed successfully!${NC}"
