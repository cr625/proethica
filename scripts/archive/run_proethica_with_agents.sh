#!/bin/bash
# run_proethica_with_agents.sh
#
# Comprehensive script to run the Proethica service with agent orchestration enabled
# and proper integration with the ontology MCP server.

set -e  # Exit on error

# ANSI color codes for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Proethica Agent-Enabled Launcher ===${NC}"

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file not found!${NC}"
    echo -e "Creating one from .env.example..."
    cp .env.example .env
    echo -e "${YELLOW}Please update the .env file with your credentials before continuing.${NC}"
    exit 1
fi

# Ensure the MCP environment variables are set in .env
if ! grep -q "MCP_SERVER_URL" .env; then
    echo -e "${YELLOW}Adding MCP_SERVER_URL to .env file...${NC}"
    echo "MCP_SERVER_URL=http://localhost:5001" >> .env
fi

if ! grep -q "USE_AGENT_ORCHESTRATOR" .env; then
    echo -e "${YELLOW}Adding USE_AGENT_ORCHESTRATOR to .env file...${NC}"
    echo "USE_AGENT_ORCHESTRATOR=true" >> .env
fi

# Ensure scripts are executable
echo -e "${BLUE}Ensuring scripts are executable...${NC}"
chmod +x run_with_agents_gunicorn.sh
chmod +x scripts/restart_mcp_server_gunicorn.fixed.sh

# Check if ontology files exist
echo -e "${BLUE}Checking ontology files...${NC}"
ONTOLOGY_DIR="mcp/ontology"
ONTOLOGY_FILES=("engineering_ethics.ttl" "nj_legal_ethics.ttl" "tccc.ttl")

for file in "${ONTOLOGY_FILES[@]}"; do
    if [ -f "$ONTOLOGY_DIR/$file" ]; then
        echo -e "${GREEN}✓ Found $file${NC}"
    else
        echo -e "${RED}✗ Missing $file${NC}"
        echo -e "${YELLOW}Please ensure all ontology files are present in $ONTOLOGY_DIR/${NC}"
    fi
done

# Check if MCP server or gunicorn is already running
echo -e "${BLUE}Checking for running processes...${NC}"
if pgrep -f "http_ontology_mcp_server.py" > /dev/null; then
    echo -e "${YELLOW}MCP server is already running. Stopping it...${NC}"
    pkill -f "http_ontology_mcp_server.py"
fi

if pgrep -f "gunicorn.*app:create_app" > /dev/null; then
    echo -e "${YELLOW}Gunicorn is already running. Stopping it...${NC}"
    pkill -f "gunicorn.*app:create_app"
fi

# Make sure ports are available
echo -e "${BLUE}Checking if ports are available...${NC}"
if lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null ; then
    echo -e "${RED}Error: Port 5001 is already in use!${NC}"
    echo -e "Please stop the service using this port and try again."
    exit 1
fi

if lsof -Pi :5000 -sTCP:LISTEN -t >/dev/null ; then
    echo -e "${RED}Error: Port 5000 is already in use!${NC}"
    echo -e "Please stop the service using this port and try again."
    exit 1
fi

# Start the MCP server
echo -e "${BLUE}Starting the MCP server...${NC}"
./scripts/restart_mcp_server_gunicorn.fixed.sh

# Wait for MCP server to initialize
echo -e "${BLUE}Waiting for the MCP server to initialize...${NC}"
sleep 5

# Verify MCP server is running
if ! lsof -Pi :5001 -sTCP:LISTEN -t >/dev/null ; then
    echo -e "${RED}Error: MCP server failed to start on port 5001!${NC}"
    echo -e "Check the logs in mcp/server_gunicorn.log for details."
    exit 1
fi

echo -e "${GREEN}MCP server is running on port 5001${NC}"

# Load environment variables from .env
echo -e "${BLUE}Loading environment variables...${NC}"
export $(grep -v '^#' .env | xargs)

# Start the Proethica application with Gunicorn
echo -e "${BLUE}Starting Proethica with agents enabled...${NC}"
echo -e "MCP_SERVER_URL=$MCP_SERVER_URL"
echo -e "USE_AGENT_ORCHESTRATOR=$USE_AGENT_ORCHESTRATOR"

# Modify the run_with_agents_gunicorn.sh script to use our fixed MCP restart script
sed -i 's|./scripts/restart_mcp_server_gunicorn.sh|./scripts/restart_mcp_server_gunicorn.fixed.sh|g' run_with_agents_gunicorn.sh

# Run the application with the agent orchestrator enabled
./run_with_agents_gunicorn.sh

echo -e "${GREEN}Setup complete!${NC}"
echo -e "${BLUE}Proethica is running at: http://localhost:5000${NC}"
echo -e "${BLUE}MCP Server is running at: http://localhost:5001${NC}"
echo -e "\nTo test the MCP server, try:"
echo -e "curl http://localhost:5001/api/ontology/engineering_ethics.ttl/entities"
