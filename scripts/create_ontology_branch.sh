#!/bin/bash

# Script to create and set up an ontology-focused branch based on realm-integration

# Color definitions
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default branch name
DEFAULT_BRANCH_NAME="ontology-focused"

# Get branch name from first argument, or use default
BRANCH_NAME=${1:-$DEFAULT_BRANCH_NAME}

echo -e "${BLUE}Creating ontology-focused branch '${YELLOW}${BRANCH_NAME}${BLUE}' based on realm-integration...${NC}"

# Check if there are uncommitted changes
if [[ -n $(git status -s) ]]; then
    echo -e "${YELLOW}Warning: You have uncommitted changes.${NC}"
    read -p "Do you want to proceed anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Aborting branch creation.${NC}"
        exit 1
    fi
    echo -e "${YELLOW}Proceeding with uncommitted changes. These changes will be carried to the new branch.${NC}"
fi

# Check if realm-integration branch exists
if ! git show-ref --verify --quiet refs/heads/realm-integration; then
    echo -e "${RED}Error: realm-integration branch does not exist.${NC}"
    exit 1
fi

# Check if target branch already exists
if git show-ref --verify --quiet refs/heads/$BRANCH_NAME; then
    echo -e "${YELLOW}Warning: Branch '${BRANCH_NAME}' already exists.${NC}"
    read -p "Do you want to use it anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${RED}Aborting branch creation.${NC}"
        exit 1
    fi
    echo -e "${BLUE}Checking out existing branch '${YELLOW}${BRANCH_NAME}${BLUE}'...${NC}"
    git checkout $BRANCH_NAME
else
    # Create new branch based on realm-integration
    echo -e "${BLUE}Creating branch '${YELLOW}${BRANCH_NAME}${BLUE}' based on realm-integration...${NC}"
    git checkout -b $BRANCH_NAME realm-integration
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create branch.${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}Branch '${YELLOW}${BRANCH_NAME}${GREEN}' is now active.${NC}"

# Create required ontology-focused files
echo -e "${BLUE}Setting up ontology-focused files...${NC}"

# Create start/stop scripts for the unified ontology server if they don't exist
if [ ! -f "start_unified_ontology_server.sh" ]; then
    echo -e "${BLUE}Creating start_unified_ontology_server.sh...${NC}"
    cat > start_unified_ontology_server.sh <<'EOF'
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
EOF
    chmod +x start_unified_ontology_server.sh
fi

if [ ! -f "stop_unified_ontology_server.sh" ]; then
    echo -e "${BLUE}Creating stop_unified_ontology_server.sh...${NC}"
    cat > stop_unified_ontology_server.sh <<'EOF'
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
EOF
    chmod +x stop_unified_ontology_server.sh
fi

# Create temporal module file if it doesn't exist
if [ ! -f "mcp/modules/temporal_module.py" ]; then
    echo -e "${BLUE}Creating temporal module...${NC}"
    mkdir -p mcp/modules
    touch mcp/modules/temporal_module.py
    chmod +x mcp/modules/temporal_module.py
fi

# Create or update ONTOLOGY_ENHANCEMENT_README.md
echo -e "${BLUE}Creating ONTOLOGY_ENHANCEMENT_README.md...${NC}"
cat > ONTOLOGY_ENHANCEMENT_README.md <<'EOF'
# Ontology Enhancement Branch

This branch focuses on enhancing the ontology functionality within ProEthica, particularly for engineering ethics applications. It builds on the REALM integration work and implements McLaren's approach to case analysis and ethical reasoning.

## Overview

The ontology enhancement focuses on:

1. **Case Representation**: Implementing temporal representation of ethics cases
2. **Extensional Definitions**: Using concrete examples to define ethical principles
3. **Case-Based Reasoning**: Finding similarities between cases to guide ethical analysis
4. **Operationalization**: Making abstract principles concrete through specific case examples

## Setup

1. **Clone this branch**:
   ```bash
   git checkout ontology-enhancement-v1
   ```

2. **Set up the environment**:
   ```bash
   python -m pip install -r requirements.txt
   ```

3. **Start the unified ontology server**:
   ```bash
   ./start_unified_ontology_server.sh
   ```

## Architecture

The implementation follows a modular architecture with the following components:

1. **Unified Ontology Server**: Provides ontology access and query capabilities
2. **Case Analysis Module**: Extracts ontology entities from cases and performs analysis
3. **Temporal Module**: Manages temporal aspects of case representation
4. **Database Layer**: Stores case analysis results and relationships
5. **API Integration**: Connects the Flask application to the ontology system

## Key Improvements

- **Modular Architecture**: Better organized code with clear separation of concerns
- **Temporal Functionality**: Integrated temporal functionality directly into the unified server architecture
- **Enhanced Case Analysis**: Support for analyzing engineering ethics cases with ontology support
- **Better Documentation**: Comprehensive documentation of the ontology case analysis methodology

## Usage

To use the ontology case analysis functionality:

1. Start the unified ontology server:
   ```bash
   ./start_unified_ontology_server.sh
   ```

2. Access the case analysis tools through the Flask API at:
   ```
   http://localhost:5000/api/ontology/analyze_case/{id}
   ```

3. Stop the server when done:
   ```bash
   ./stop_unified_ontology_server.sh
   ```

## References

- McLaren, B. M. (2003). Extensionally Defining Principles and Cases in Ethics: An AI Model. Artificial Intelligence Journal, 150, 145-181.
EOF

# Create the documentation directory and case analysis plan if it doesn't exist
mkdir -p docs
if [ ! -f "docs/ontology_case_analysis_plan.md" ]; then
    echo -e "${BLUE}Creating ontology case analysis plan...${NC}"
    touch docs/ontology_case_analysis_plan.md
fi

# Modify CLAUDE.md to include the branch information
if [ -f "CLAUDE.md" ]; then
    echo -e "${BLUE}Updating CLAUDE.md...${NC}"
    # We'll let the user manually update this file
fi

# Final steps
echo -e "${BLUE}Making scripts executable...${NC}"
chmod +x start_unified_ontology_server.sh stop_unified_ontology_server.sh 2>/dev/null

echo
echo -e "${GREEN}Setup complete!${NC}"
echo -e "${BLUE}Branch '${YELLOW}${BRANCH_NAME}${BLUE}' is ready for ontology enhancement development.${NC}"
echo -e "${BLUE}To start the unified ontology server: ${YELLOW}./start_unified_ontology_server.sh${NC}"
echo -e "${BLUE}For implementation details, see: ${YELLOW}docs/ontology_case_analysis_plan.md${NC}"
