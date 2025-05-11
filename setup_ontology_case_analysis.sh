#!/bin/bash
# Setup script for the ontology case analysis environment
# This script:
# 1. Creates the necessary git branch
# 2. Sets up the database schema
# 3. Verifies the connectivity between ProEthica and the unified ontology server

# Set script to exit on error
set -e

# Define colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${YELLOW}Setting up ontology case analysis environment...${NC}"

# Step 1: Create the git branch if it doesn't already exist
echo -e "${YELLOW}Step 1: Creating git branch...${NC}"
if [ -f ./create_ontology_branch.sh ]; then
    chmod +x ./create_ontology_branch.sh
    ./create_ontology_branch.sh
else
    echo -e "${RED}Error: create_ontology_branch.sh not found${NC}"
    exit 1
fi

# Step 2: Set up the database schema
echo -e "${YELLOW}Step 2: Setting up database schema...${NC}"
if [ -f ./scripts/create_case_analysis_tables.py ]; then
    python ./scripts/create_case_analysis_tables.py
    if [ $? -ne 0 ]; then
        echo -e "${RED}Error: Failed to create database tables${NC}"
        exit 1
    fi
    echo -e "${GREEN}Database schema set up successfully${NC}"
else
    echo -e "${RED}Error: create_case_analysis_tables.py not found${NC}"
    exit 1
fi

# Step 3: Check if the unified ontology server needs to be started
echo -e "${YELLOW}Step 3: Starting unified ontology server (if not already running)...${NC}"

# Check if the server is already running
SERVER_PORT=$(grep MCP_SERVER_PORT .env 2>/dev/null | cut -d '=' -f2 || echo "5001")
if curl -s http://localhost:${SERVER_PORT}/info > /dev/null 2>&1; then
    echo -e "${GREEN}Unified ontology server is already running${NC}"
else
    echo "Starting unified ontology server..."
    
    # Check if the start script exists
    if [ -f ./start_unified_ontology_server.sh ]; then
        chmod +x ./start_unified_ontology_server.sh
        ./start_unified_ontology_server.sh &
        
        # Wait for the server to start
        MAX_RETRIES=10
        RETRY_COUNT=0
        while ! curl -s http://localhost:${SERVER_PORT}/info > /dev/null 2>&1; do
            sleep 1
            RETRY_COUNT=$((RETRY_COUNT + 1))
            if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
                echo -e "${RED}Error: Failed to start unified ontology server${NC}"
                exit 1
            fi
        done
        
        echo -e "${GREEN}Unified ontology server started successfully${NC}"
    else
        # Alternative: use the Python script directly
        if [ -f ./run_unified_mcp_server.py ]; then
            echo "Starting server using run_unified_mcp_server.py..."
            python ./run_unified_mcp_server.py &
            
            # Wait for the server to start
            MAX_RETRIES=10
            RETRY_COUNT=0
            while ! curl -s http://localhost:${SERVER_PORT}/info > /dev/null 2>&1; do
                sleep 1
                RETRY_COUNT=$((RETRY_COUNT + 1))
                if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
                    echo -e "${RED}Error: Failed to start unified ontology server${NC}"
                    exit 1
                fi
            done
            
            echo -e "${GREEN}Unified ontology server started successfully${NC}"
        else
            echo -e "${RED}Error: Could not find scripts to start the unified ontology server${NC}"
            exit 1
        fi
    fi
fi

# Step 4: Verify connectivity
echo -e "${YELLOW}Step 4: Verifying connectivity between ProEthica and ontology server...${NC}"
if [ -f ./scripts/verify_proethica_ontology.py ]; then
    python ./scripts/verify_proethica_ontology.py
    
    # Check the verification result
    VERIFY_RESULT=$?
    if [ $VERIFY_RESULT -eq 0 ]; then
        echo -e "${GREEN}Verification completed successfully${NC}"
    elif [ $VERIFY_RESULT -eq 1 ]; then
        echo -e "${YELLOW}Verification incomplete. Follow the instructions above to complete setup.${NC}"
    else
        echo -e "${RED}Verification failed. See errors above.${NC}"
        exit 1
    fi
else
    echo -e "${RED}Error: verify_proethica_ontology.py not found${NC}"
    exit 1
fi

# Step 5: Display success message and next steps
echo
echo -e "${GREEN}Ontology case analysis environment setup completed!${NC}"
echo
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Implement additional case analysis components"
echo "2. Create UI elements for displaying case analyses"
echo "3. Run test cases to verify functionality"
echo
echo -e "${YELLOW}To start working with case analysis, run:${NC}"
echo "python ./test_case_analysis.py"
