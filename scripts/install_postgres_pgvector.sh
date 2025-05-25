#!/bin/bash
# Script to install PostgreSQL with pgvector in codespace

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}===================================================${NC}"
echo -e "${YELLOW}INSTALLING POSTGRESQL WITH PGVECTOR IN CODESPACE${NC}"
echo -e "${BLUE}===================================================${NC}"

# Define database constants
POSTGRES_VERSION="15"
POSTGRES_USER="postgres"
POSTGRES_DB="ai_ethical_dm"

# Step 1: Install PostgreSQL
echo -e "${YELLOW}Installing PostgreSQL ${POSTGRES_VERSION}...${NC}"
sudo apt-get update
sudo apt-get install -y postgresql-${POSTGRES_VERSION} postgresql-server-dev-${POSTGRES_VERSION} build-essential git

# Step 2: Start PostgreSQL service
echo -e "${YELLOW}Starting PostgreSQL service...${NC}"
sudo service postgresql start
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to start PostgreSQL service. Please check logs.${NC}"
    exit 1
fi
echo -e "${GREEN}PostgreSQL service started successfully${NC}"

# Step 3: Install pgvector
echo -e "${YELLOW}Installing pgvector extension...${NC}"
git clone --branch v0.7.0 https://github.com/pgvector/pgvector.git /tmp/pgvector
cd /tmp/pgvector
make
sudo make install
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to install pgvector extension. Please check logs.${NC}"
    exit 1
fi
echo -e "${GREEN}pgvector extension installed successfully${NC}"

# Step 4: Create database
echo -e "${YELLOW}Creating database '${POSTGRES_DB}'...${NC}"
sudo -u postgres psql -c "CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};"
if [ $? -ne 0 ]; then
    # Database might already exist
    echo -e "${YELLOW}Database might already exist, continuing...${NC}"
fi

# Step 5: Enable pgvector extension on the database
echo -e "${YELLOW}Enabling pgvector extension on database '${POSTGRES_DB}'...${NC}"
sudo -u postgres psql -d ${POSTGRES_DB} -c "CREATE EXTENSION IF NOT EXISTS vector;"
if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to enable pgvector extension. Please check logs.${NC}"
    exit 1
fi
echo -e "${GREEN}pgvector extension enabled successfully${NC}"

# Step 6: Update or create .env file with PostgreSQL connection
if [ -f ".env" ]; then
    echo -e "${YELLOW}Updating DATABASE_URL in .env file...${NC}"
    sed -i "s|DATABASE_URL=.*|DATABASE_URL=postgresql://${POSTGRES_USER}@localhost:5432/${POSTGRES_DB}|g" .env
    
    # Update ENVIRONMENT in .env file
    if grep -q "ENVIRONMENT" .env; then
        echo -e "${YELLOW}Updating ENVIRONMENT in .env file...${NC}"
        sed -i "s|ENVIRONMENT=.*|ENVIRONMENT=codespace|g" .env
    else
        echo -e "${YELLOW}Adding ENVIRONMENT to .env file...${NC}"
        echo "ENVIRONMENT=codespace" >> .env
    fi
else
    echo -e "${YELLOW}Creating .env file...${NC}"
    echo "DATABASE_URL=postgresql://${POSTGRES_USER}@localhost:5432/${POSTGRES_DB}" > .env
    echo "ENVIRONMENT=codespace" >> .env
    echo "USE_MOCK_GUIDELINE_RESPONSES=true" >> .env
    echo -e "${GREEN}Created .env file${NC}"
fi

# Step 7: Verify database connection
echo -e "${BLUE}Checking database connection...${NC}"
sudo -u postgres psql -d ${POSTGRES_DB} -c "\conninfo"
if [ $? -ne 0 ]; then
    echo -e "${RED}Database connection failed. Please check connection parameters.${NC}"
    exit 1
fi
echo -e "${GREEN}Database connection successful!${NC}"

# Step 8: Verify pgvector extension is enabled in the database
echo -e "${BLUE}Verifying pgvector extension is enabled...${NC}"
PGVECTOR_ENABLED=$(sudo -u postgres psql -d ${POSTGRES_DB} -t -c "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector';")
if [[ $PGVECTOR_ENABLED == *"1"* ]]; then
    echo -e "${GREEN}pgvector extension is properly enabled on database '${POSTGRES_DB}'${NC}"
else
    echo -e "${RED}pgvector extension is NOT enabled on database '${POSTGRES_DB}'${NC}"
    echo -e "${YELLOW}Try enabling it manually:${NC}"
    echo -e "sudo -u postgres psql -d ${POSTGRES_DB} -c \"CREATE EXTENSION IF NOT EXISTS vector;\""
fi

echo -e "${BLUE}===================================================${NC}"
echo -e "${GREEN}POSTGRESQL WITH PGVECTOR INSTALLATION COMPLETE${NC}"
echo -e "${BLUE}===================================================${NC}"
echo -e "${GREEN}Database connection: postgresql://${POSTGRES_USER}@localhost:5432/${POSTGRES_DB}${NC}"
echo -e "${YELLOW}To run commands as postgres user, use: sudo -u postgres psql${NC}"
echo -e "${YELLOW}To connect to the database, use: sudo -u postgres psql -d ${POSTGRES_DB}${NC}"
echo -e "${BLUE}===================================================${NC}"
