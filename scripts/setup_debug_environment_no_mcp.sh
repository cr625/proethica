#!/bin/bash
# Setup ProEthica Debug Environment (No MCP)
# This script sets up the environment for debugging, but does NOT start the MCP server.

set -e

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Source environment variables if needed
if [ -f "/workspaces/ai-ethical-dm/.env" ]; then
    source /workspaces/ai-ethical-dm/.env
fi

# Environment detection (mimic start_proethica_updated.sh)
if [ "$CODESPACES" == "true" ]; then
    ENV="codespace"
    POSTGRES_CONTAINER="postgres17-pgvector-codespace"
elif grep -qi microsoft /proc/version 2>/dev/null; then
    ENV="wsl"
    POSTGRES_CONTAINER="postgres17-pgvector-wsl"
else
    ENV="development"
    POSTGRES_CONTAINER="postgres17-pgvector"
fi

# Check Docker and PostgreSQL container
if ! command -v docker &> /dev/null; then
    echo -e "${YELLOW}Docker is not installed or not in PATH. Skipping Docker checks.${NC}"
else
    CONTAINER_STATUS=$(docker ps -a --filter "name=$POSTGRES_CONTAINER" --format "{{.Status}}")
    if [ -z "$CONTAINER_STATUS" ]; then
        echo -e "${YELLOW}PostgreSQL container '$POSTGRES_CONTAINER' not found. Setting up shared PostgreSQL container...${NC}"
        ./scripts/setup_shared_postgres.sh
    else
        if [[ $CONTAINER_STATUS == Exited* ]] || [[ $CONTAINER_STATUS == Created* ]]; then
            echo -e "${YELLOW}PostgreSQL container '$POSTGRES_CONTAINER' exists but is not running. Starting it now...${NC}"
            if docker start $POSTGRES_CONTAINER; then
                echo -e "${GREEN}PostgreSQL container started successfully.${NC}"
                sleep 3
            else
                echo -e "${RED}Failed to start PostgreSQL container. Please check Docker logs.${NC}"
            fi
        else
            echo -e "${GREEN}PostgreSQL container '$POSTGRES_CONTAINER' is already running.${NC}"
        fi
    fi
fi

# Initialize the database (if needed)
if [ -f "/workspaces/ai-ethical-dm/scripts/init_db.sh" ]; then
    bash /workspaces/ai-ethical-dm/scripts/init_db.sh
fi

# Print message for clarity
>&2 echo "[setup_debug_environment_no_mcp.sh] Environment setup complete. MCP server NOT started."
