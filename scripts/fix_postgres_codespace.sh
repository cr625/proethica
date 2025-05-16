#!/bin/bash
# Script to fix postgres container issues in codespace environment

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}===================================================${NC}"
echo -e "${YELLOW}FIXING POSTGRESQL CONTAINER FOR CODESPACE${NC}"
echo -e "${BLUE}===================================================${NC}"

# Define container constants
POSTGRES_CONTAINER="postgres17-pgvector-codespace"
POSTGRES_VERSION="17"
POSTGRES_PORT="5433"
POSTGRES_USER="postgres"
POSTGRES_PASSWORD="PASS"
POSTGRES_DB="ai_ethical_dm"

# Step 1: Stop and remove any existing containers with the same name
echo -e "${YELLOW}Stopping and removing any existing PostgreSQL containers...${NC}"
docker stop $POSTGRES_CONTAINER 2>/dev/null || true
docker rm -f $POSTGRES_CONTAINER 2>/dev/null || true
echo -e "${GREEN}Removed any existing containers.${NC}"

# Step 2: Check for the image and remove if needed
echo -e "${YELLOW}Checking for old PostgreSQL images...${NC}"
if docker images | grep -q "postgres-pgvector"; then
    echo -e "${YELLOW}Found existing postgres-pgvector image. Will rebuild.${NC}"
    docker rmi postgres-pgvector:$POSTGRES_VERSION 2>/dev/null || true
fi

# Step 3: Check for and remove any stale Docker networks
echo -e "${YELLOW}Cleaning up any stale Docker networks...${NC}"
docker network prune -f

# Step 4: Check and clean up Docker volumes
echo -e "${YELLOW}Checking for orphaned Docker volumes...${NC}"
ORPHANED_VOLUMES=$(docker volume ls -qf dangling=true)
if [ ! -z "$ORPHANED_VOLUMES" ]; then
    echo -e "${YELLOW}Found orphaned volumes. Removing...${NC}"
    docker volume rm $ORPHANED_VOLUMES 2>/dev/null || true
fi

# Step 5: Build and start fresh container
echo -e "${YELLOW}Building PostgreSQL image with pgvector from Dockerfile...${NC}"
if [ -f "./postgres.Dockerfile" ]; then
    docker build -t postgres-pgvector:$POSTGRES_VERSION -f postgres.Dockerfile . || {
        echo -e "${RED}Failed to build Docker image. Please check Dockerfile.${NC}"
        exit 1
    }
    
    echo -e "${YELLOW}Running PostgreSQL container with pgvector...${NC}"
    docker run --name $POSTGRES_CONTAINER \
        -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
        -e POSTGRES_USER=$POSTGRES_USER \
        -e POSTGRES_DB=$POSTGRES_DB \
        -p $POSTGRES_PORT:5432 \
        -d postgres-pgvector:$POSTGRES_VERSION || {
            echo -e "${RED}Failed to start Docker container. Trying with pgvector from Docker Hub instead.${NC}"
            docker run --name $POSTGRES_CONTAINER \
                -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
                -e POSTGRES_USER=$POSTGRES_USER \
                -e POSTGRES_DB=$POSTGRES_DB \
                -p $POSTGRES_PORT:5432 \
                -d pgvector/pgvector:pg$POSTGRES_VERSION || {
                    echo -e "${RED}Failed to start container from pgvector/pgvector:pg$POSTGRES_VERSION.${NC}"
                    exit 1
                }
        }
else
    echo -e "${YELLOW}postgres.Dockerfile not found, using pgvector image from Docker Hub...${NC}"
    docker run --name $POSTGRES_CONTAINER \
        -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
        -e POSTGRES_USER=$POSTGRES_USER \
        -e POSTGRES_DB=$POSTGRES_DB \
        -p $POSTGRES_PORT:5432 \
        -d pgvector/pgvector:pg$POSTGRES_VERSION || {
            echo -e "${RED}Failed to start container from pgvector/pgvector:pg$POSTGRES_VERSION.${NC}"
            exit 1
        }
fi

# Step 6: Wait for container to initialize
echo -e "${YELLOW}Waiting for PostgreSQL to initialize (30 seconds)...${NC}"
sleep 10
echo -e "${YELLOW}⏳ Still waiting... (20 seconds remaining)${NC}"
sleep 10
echo -e "${YELLOW}⏳ Almost there... (10 seconds remaining)${NC}"
sleep 10

# Step 7: Verify container is running
if [ "$(docker ps -q -f name=$POSTGRES_CONTAINER)" ]; then
    echo -e "${GREEN}PostgreSQL container is now running on port $POSTGRES_PORT.${NC}"
    
    # Wait a bit more to ensure PostgreSQL is fully initialized
    sleep 5
    
    # Initialize pgvector extension
    echo -e "${YELLOW}Initializing pgvector extension...${NC}"
    docker exec -i $POSTGRES_CONTAINER psql -U $POSTGRES_USER -d $POSTGRES_DB -c 'CREATE EXTENSION IF NOT EXISTS pgvector;' || {
        echo -e "${RED}Failed to initialize pgvector extension. PostgreSQL might not be fully started yet.${NC}"
        echo -e "${YELLOW}Will try again in 10 seconds...${NC}"
        sleep 10
        docker exec -i $POSTGRES_CONTAINER psql -U $POSTGRES_USER -d $POSTGRES_DB -c 'CREATE EXTENSION IF NOT EXISTS pgvector;' || {
            echo -e "${RED}Still failed to initialize pgvector extension.${NC}"
            echo -e "${RED}Please check the container logs for more details:${NC}"
            docker logs $POSTGRES_CONTAINER
        }
    }
    
    # Ensure password is set correctly
    echo -e "${YELLOW}Ensuring database password is set to PASS...${NC}"
    docker exec -i $POSTGRES_CONTAINER psql -U $POSTGRES_USER -c "ALTER USER postgres WITH PASSWORD 'PASS';"
    
    # Run initialization script if it exists
    if [ -f "./init-pgvector.sql" ]; then
        echo -e "${YELLOW}Running init-pgvector.sql initialization script...${NC}"
        docker exec -i $POSTGRES_CONTAINER psql -U $POSTGRES_USER -d $POSTGRES_DB < ./init-pgvector.sql
    fi
    
    # Update or create .env file
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
        }
    else
        echo -e "${YELLOW}No .env file found. Creating one...${NC}"
        echo "DATABASE_URL=postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:$POSTGRES_PORT/$POSTGRES_DB" > .env
        echo "ENVIRONMENT=codespace" >> .env
        echo "USE_MOCK_GUIDELINE_RESPONSES=true" >> .env
    fi
    
    # Show container status
    echo -e "${BLUE}Container details:${NC}"
    docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" -f name=$POSTGRES_CONTAINER
    
    echo -e "${GREEN}PostgreSQL with pgvector has been successfully fixed and set up!${NC}"
else
    echo -e "${RED}Failed to start PostgreSQL container. Container details:${NC}"
    docker ps -a -f name=$POSTGRES_CONTAINER
    echo -e "${RED}Container logs:${NC}"
    docker logs $POSTGRES_CONTAINER
    exit 1
fi

echo -e "${BLUE}===================================================${NC}"
echo -e "${GREEN}POSTGRESQL CONTAINER FIX COMPLETE${NC}"
echo -e "${BLUE}===================================================${NC}"
