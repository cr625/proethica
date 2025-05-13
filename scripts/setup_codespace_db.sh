#!/bin/bash
# Setup PostgreSQL for GitHub Codespaces environment

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}Setting up PostgreSQL for GitHub Codespaces environment...${NC}"

# Check if we're in a GitHub Codespace
if [ "$CODESPACES" != "true" ]; then
    echo -e "${RED}This script should only be run in a GitHub Codespace environment.${NC}"
    exit 1
fi

# Get current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Ensure Docker is installed and running
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed or not in PATH. Please install Docker.${NC}"
    exit 1
fi

# Define PostgreSQL container details
POSTGRES_CONTAINER="postgres17-pgvector-codespace"
POSTGRES_VERSION="15"
POSTGRES_PORT="5433"
POSTGRES_USER="postgres"
POSTGRES_PASSWORD="PASS"
POSTGRES_DB="ai_ethical_dm"

# Check if the PostgreSQL container is already running
if [ "$(docker ps -q -f name=$POSTGRES_CONTAINER)" ]; then
    echo -e "${GREEN}PostgreSQL container '$POSTGRES_CONTAINER' is already running.${NC}"
else
    # Check if the container exists but is not running
    if [ "$(docker ps -aq -f name=$POSTGRES_CONTAINER)" ]; then
        echo -e "${YELLOW}PostgreSQL container '$POSTGRES_CONTAINER' exists but is not running. Starting it now...${NC}"
        docker start $POSTGRES_CONTAINER
    else
        # Create and start a new PostgreSQL container
        echo -e "${YELLOW}Creating new PostgreSQL container with pgvector extension...${NC}"
        
        # Check if postgres.Dockerfile exists
        if [ -f "postgres.Dockerfile" ]; then
            echo -e "${YELLOW}Building PostgreSQL image with pgvector from Dockerfile...${NC}"
            docker build -t postgres-pgvector:$POSTGRES_VERSION -f postgres.Dockerfile .
            
            echo -e "${YELLOW}Running PostgreSQL container with pgvector...${NC}"
            docker run --name $POSTGRES_CONTAINER \
                -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
                -e POSTGRES_DB=$POSTGRES_DB \
                -p $POSTGRES_PORT:5432 \
                -d postgres-pgvector:$POSTGRES_VERSION
        else
            echo -e "${YELLOW}Using PostgreSQL 15 with pgvector extension from Docker Hub...${NC}"
            docker run --name $POSTGRES_CONTAINER \
                -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
                -e POSTGRES_DB=$POSTGRES_DB \
                -p $POSTGRES_PORT:5432 \
                -d ankane/pgvector:v0.5.1
        fi
    fi
    
    # Wait for PostgreSQL to start
    echo -e "${YELLOW}Waiting for PostgreSQL to initialize...${NC}"
    sleep 5
fi

# Check if PostgreSQL is running
if [ "$(docker ps -q -f name=$POSTGRES_CONTAINER)" ]; then
    echo -e "${GREEN}PostgreSQL container is running on port $POSTGRES_PORT.${NC}"
    
    # Check if .env file exists
    if [ -f ".env" ]; then
        # Update DATABASE_URL in .env file
        if grep -q "DATABASE_URL" .env; then
            echo -e "${YELLOW}Updating DATABASE_URL in .env file...${NC}"
            sed -i "s|DATABASE_URL=.*|DATABASE_URL=postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:$POSTGRES_PORT/$POSTGRES_DB|g" .env
        else
            echo -e "${YELLOW}Adding DATABASE_URL to .env file...${NC}"
            echo "DATABASE_URL=postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:$POSTGRES_PORT/$POSTGRES_DB" >> .env
        fi
        
        # Update ENVIRONMENT in .env file
        if grep -q "ENVIRONMENT" .env; then
            echo -e "${YELLOW}Updating ENVIRONMENT in .env file...${NC}"
            sed -i "s|ENVIRONMENT=.*|ENVIRONMENT=codespace|g" .env
        else
            echo -e "${YELLOW}Adding ENVIRONMENT to .env file...${NC}"
            echo "ENVIRONMENT=codespace" >> .env
        fi
    else
        echo -e "${YELLOW}No .env file found. Creating one...${NC}"
        echo "DATABASE_URL=postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:$POSTGRES_PORT/$POSTGRES_DB" > .env
        echo "ENVIRONMENT=codespace" >> .env
    fi
    
    # Initialize the database with pgvector extension
    echo -e "${YELLOW}Initializing pgvector extension...${NC}"
    docker exec -it $POSTGRES_CONTAINER psql -U $POSTGRES_USER -d $POSTGRES_DB -c 'CREATE EXTENSION IF NOT EXISTS pgvector;'
    
    # Check if init-pgvector.sql exists
    if [ -f "init-pgvector.sql" ]; then
        echo -e "${YELLOW}Running init-pgvector.sql initialization script...${NC}"
        docker exec -i $POSTGRES_CONTAINER psql -U $POSTGRES_USER -d $POSTGRES_DB < init-pgvector.sql
    fi
    
    echo -e "${GREEN}PostgreSQL with pgvector has been successfully set up in codespace environment!${NC}"
else
    echo -e "${RED}Failed to start PostgreSQL container. Please check Docker logs.${NC}"
    docker logs $POSTGRES_CONTAINER
    exit 1
fi
