#!/bin/bash

# Color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== PostgreSQL Password Fix Script ===${NC}"
echo -e "${YELLOW}This script will change the PostgreSQL password for user 'postgres' to 'PASS'${NC}"

# Check if running in Codespace
if [ "$CODESPACES" != "true" ]; then
    echo -e "${RED}This script is intended to run in GitHub Codespaces environment only.${NC}"
    echo -e "${YELLOW}If you're in Codespaces but this check failed, you can continue anyway.${NC}"
    read -p "Continue anyway? (y/n): " decision
    if [[ ! $decision =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Operation cancelled.${NC}"
        exit 0
    fi
fi

# Use the specific PostgreSQL container for Codespaces
echo -e "${BLUE}Using PostgreSQL container for Codespaces...${NC}"
CONTAINER="postgres17-pgvector-codespace"

# Check if the container exists and is running
if ! docker ps | grep -q "$CONTAINER"; then
    echo -e "${RED}Container $CONTAINER is not running.${NC}"
    echo -e "${YELLOW}Checking if it exists but is stopped...${NC}"
    
    if docker ps -a | grep -q "$CONTAINER"; then
        echo -e "${YELLOW}Container exists but is not running. Attempting to start it...${NC}"
        docker start "$CONTAINER"
        sleep 3  # Give it time to start
    else
        echo -e "${RED}Container $CONTAINER not found.${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}Using PostgreSQL container: $CONTAINER${NC}"

# First check if we can connect with the PASS password
echo -e "${YELLOW}Checking if current password is already 'PASS'...${NC}"
if docker exec -i $CONTAINER psql -U postgres -d ai_ethical_dm -c "SELECT 1" 2>/dev/null; then
    echo -e "${GREEN}Password is already set to 'PASS'. No changes needed.${NC}"
else
    # Change the password in the PostgreSQL container
    echo -e "${YELLOW}Changing PostgreSQL password for user 'postgres' to 'PASS'...${NC}"
    # The default password is usually 'postgres' in Codespaces
    docker exec -i $CONTAINER psql -U postgres -c "ALTER USER postgres WITH PASSWORD 'PASS';" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Password successfully changed to 'PASS'${NC}"
        echo -e "${BLUE}You should now be able to run start_proethica_updated.sh without password issues${NC}"
    else
        echo -e "${RED}Failed to change password with default credentials.${NC}"
        echo -e "${YELLOW}Trying with password 'postgres'...${NC}"
        
        # Try using PGPASSWORD to supply the default password
        PGPASSWORD=postgres docker exec -i $CONTAINER psql -U postgres -c "ALTER USER postgres WITH PASSWORD 'PASS';" 2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}Password successfully changed to 'PASS'${NC}"
            echo -e "${BLUE}You should now be able to run start_proethica_updated.sh without password issues${NC}"
        else
            echo -e "${RED}Failed to change password. Please check if the PostgreSQL service is running.${NC}"
            exit 1
        fi
    fi
fi

echo -e "${YELLOW}Note: This change is temporary and will be reset if the container is recreated.${NC}"
