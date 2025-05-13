#!/bin/bash
#
# Script to start ProEthica with guidelines support and debug interface
# in GitHub Codespaces environment

set -e  # Exit on error

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== ProEthica Starter with Guidelines Support and Debug Interface ===${NC}"
echo -e "${YELLOW}Starting ProEthica with debug capabilities...${NC}"

# Check if we're in Codespaces
if [ "$CODESPACES" == "true" ]; then
    echo -e "${BLUE}Detected GitHub Codespaces environment...${NC}"
else
    echo -e "${YELLOW}Not running in GitHub Codespaces. Some features may not work as expected.${NC}"
fi

# Start the main application with guidelines support
if [ -f "./start_proethica_updated.sh" ]; then
    echo -e "${BLUE}Starting ProEthica with enhanced guidelines support...${NC}"
    
    # Make the script executable if it's not
    if [ ! -x "./start_proethica_updated.sh" ]; then
        chmod +x ./start_proethica_updated.sh
    fi
    
    # Export DEBUG_INTERFACE flag to enable debug features
    export ENABLE_DEBUG_INTERFACE=true
    echo -e "${YELLOW}Enabled debug interface with ENABLE_DEBUG_INTERFACE=true${NC}"
    
    # Run the startup script
    ./start_proethica_updated.sh &
    MAIN_APP_PID=$!
    
    echo -e "${GREEN}Main application started in background. PID: ${MAIN_APP_PID}${NC}"
    
    # Wait a moment for the application to start
    echo -e "${YELLOW}Waiting for services to initialize...${NC}"
    sleep 10
    
    # Check if MCP server is running
    echo -e "${BLUE}Checking MCP server status...${NC}"
    if curl -s -X POST http://localhost:5001/jsonrpc \
         -H "Content-Type: application/json" \
         -d '{"jsonrpc":"2.0","method":"list_tools","params":{},"id":1}' | grep -q "tools"; then
        echo -e "${GREEN}MCP server is running and responding correctly.${NC}"
    else
        echo -e "${RED}MCP server is not responding. Debug interface may not work correctly.${NC}"
    fi
    
    # Display access information
    echo -e "\n${BLUE}======= ProEthica Access Information =======${NC}"
    echo -e "${GREEN}Main Application URL: ${YELLOW}http://localhost:3333${NC}"
    echo -e "${GREEN}Debug Interface URL: ${YELLOW}http://localhost:3333/debug/status${NC}"
    echo -e "${GREEN}Guidelines URL: ${YELLOW}http://localhost:3333/worlds/<world_id>/guidelines${NC}"
    echo -e "${GREEN}MCP Server JSON-RPC: ${YELLOW}http://localhost:5001/jsonrpc${NC}"
    
    # Provide guideline upload instructions
    echo -e "\n${BLUE}======= Using Guidelines Feature =======${NC}"
    echo -e "1. Visit ${YELLOW}http://localhost:3333/worlds${NC} and select or create a world"
    echo -e "2. Click on the ${YELLOW}Guidelines${NC} tab"
    echo -e "3. Use the ${YELLOW}Add Guideline${NC} button to upload a new guideline"
    echo -e "4. After upload, the system will extract concepts and match them to ontology entities"
    echo -e "5. Review the matches and generate RDF triples"
    
    # Provide debug interface instructions
    echo -e "\n${BLUE}======= Using Debug Interface =======${NC}"
    echo -e "1. Visit ${YELLOW}http://localhost:3333/debug/status${NC} to see system status"
    echo -e "2. Check MCP server connections, ontology status, and database info"
    echo -e "3. Use ${YELLOW}./check_status.sh${NC} for CLI-based diagnostics"
    
    # Wait for user to press Ctrl+C
    echo -e "\n${YELLOW}Press Ctrl+C to shut down all services${NC}"
    wait $MAIN_APP_PID
else
    echo -e "${RED}Error: start_proethica_updated.sh not found!${NC}"
    echo -e "${YELLOW}Please run this script from the ProEthica root directory.${NC}"
    exit 1
fi

# Handle cleanup on exit
cleanup() {
    echo -e "\n${YELLOW}Shutting down services...${NC}"
    
    # Stop the main application process if it's still running
    if ps -p $MAIN_APP_PID > /dev/null; then
        kill $MAIN_APP_PID
    fi
    
    # Additional cleanup to ensure all related processes are stopped
    pkill -f "run_enhanced_mcp_server_with_guidelines.py" 2>/dev/null || true
    pkill -f "python.*run.py" 2>/dev/null || true
    
    echo -e "${GREEN}Services shut down successfully.${NC}"
}

trap cleanup EXIT
