#!/bin/bash
# auto_run.sh
#
# Unified startup script for ProEthica that automatically detects the environment
# (development or production) and starts the appropriate server configuration.

set -e  # Exit on error

# ANSI color codes for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== ProEthica Unified Launcher ===${NC}"

# 1. Determine environment
if [ -n "$ENVIRONMENT" ]; then
    # Use explicit environment variable if set
    ENV=$ENVIRONMENT
    echo -e "${GREEN}Using explicit environment setting: $ENV${NC}"
else
    # Check hostname
    HOSTNAME=$(hostname)
    if [[ "$HOSTNAME" == "proethica.org" || "$HOSTNAME" == prod-* ]]; then
        ENV="production"
        echo -e "${GREEN}Detected production hostname: $HOSTNAME${NC}"
    else
        # Get git branch as a hint
        BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
        if [[ "$BRANCH" == "main" || "$BRANCH" == "master" ]]; then
            ENV="production"
            echo -e "${GREEN}Detected production branch: $BRANCH${NC}"
        else
            ENV="development"
            echo -e "${GREEN}Detected development branch: $BRANCH${NC}"
        fi
    fi
fi

# Check if .env file exists and create it if necessary
if [ ! -f .env ]; then
    echo -e "${YELLOW}No .env file found. Creating one from .env.example...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}Please update the .env file with your credentials before continuing.${NC}"
fi

# Update .env with environment setting
if grep -q "^ENVIRONMENT=" .env; then
    # Replace existing ENVIRONMENT line
    sed -i "s/^ENVIRONMENT=.*/ENVIRONMENT=$ENV/" .env
else
    # Add ENVIRONMENT line if it doesn't exist
    echo "ENVIRONMENT=$ENV" >> .env
fi

# 2. Start the appropriate servers
if [ "$ENV" == "production" ]; then
    echo -e "${BLUE}Starting in PRODUCTION mode using Gunicorn...${NC}"
    
    # Ensure necessary environment variables are set in .env
    if ! grep -q "MCP_SERVER_URL" .env; then
        echo -e "${YELLOW}Adding MCP_SERVER_URL to .env file...${NC}"
        echo "MCP_SERVER_URL=http://localhost:5001" >> .env
    fi

    if ! grep -q "USE_AGENT_ORCHESTRATOR" .env; then
        echo -e "${YELLOW}Adding USE_AGENT_ORCHESTRATOR to .env file...${NC}"
        echo "USE_AGENT_ORCHESTRATOR=true" >> .env
    fi
    
    # Start using the production script
    ./run_proethica_with_agents.sh
else
    echo -e "${BLUE}Starting in DEVELOPMENT mode using Flask dev server...${NC}"
    
    # Update .env for development settings if needed
    if ! grep -q "FLASK_ENV" .env; then
        echo -e "${YELLOW}Adding FLASK_ENV to .env file...${NC}"
        echo "FLASK_ENV=development" >> .env
    else
        sed -i "s/^FLASK_ENV=.*/FLASK_ENV=development/" .env
    fi
    
    if ! grep -q "MCP_SERVER_URL" .env; then
        echo -e "${YELLOW}Adding MCP_SERVER_URL to .env file...${NC}"
        echo "MCP_SERVER_URL=http://localhost:5001" >> .env
    else
        # Update existing MCP_SERVER_URL to use port 5001
        sed -i "s|MCP_SERVER_URL=http://localhost:[0-9]*|MCP_SERVER_URL=http://localhost:5001|g" .env
    fi
    
    # Set environment variable for MCP server port
    if ! grep -q "MCP_SERVER_PORT" .env; then
        echo -e "${YELLOW}Adding MCP_SERVER_PORT to .env file...${NC}"
        echo "MCP_SERVER_PORT=5001" >> .env
    else
        sed -i "s/MCP_SERVER_PORT=.*/MCP_SERVER_PORT=5001/" .env
    fi
    
    # Handle USE_MOCK_FALLBACK setting in .env
    if ! grep -q "USE_MOCK_FALLBACK" .env; then
        echo -e "${YELLOW}Adding USE_MOCK_FALLBACK to .env file...${NC}"
        echo "USE_MOCK_FALLBACK=false" >> .env
    else
        # Do not override existing value
        echo -e "${BLUE}Using existing USE_MOCK_FALLBACK setting from .env file${NC}"
    fi
    
    # Ensure scripts are executable
    chmod +x scripts/restart_mcp_server.sh
    
    # Start the enhanced MCP server and wait for it to initialize
    echo -e "${BLUE}Starting enhanced MCP server on port 5001...${NC}"
    ./scripts/restart_mcp_server.sh
    echo -e "${BLUE}Waiting for MCP server to initialize...${NC}"
    sleep 5  # Wait for server to initialize
    
    # We no longer need to set SKIP_MCP_SERVER as we only have one MCP server implementation now
    
    # Export environment variables from .env file
    export $(grep -v '^#' .env | xargs)
    
    # Start the Flask development server with proper environment variable handling
    echo -e "${BLUE}Starting Flask development server...${NC}"
    if [ -f "./scripts/run_with_env.sh" ] && [ -x "./scripts/run_with_env.sh" ]; then
        # Use run_with_env.sh to ensure proper environment variable handling (especially for Anthropic SDK)
        ./scripts/run_with_env.sh python run.py
    else
        # Fallback to direct execution if run_with_env.sh is not available
        python run.py
    fi
fi

echo -e "${GREEN}Setup complete!${NC}"
