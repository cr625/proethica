#!/bin/bash
# Script to set up local PostgreSQL with pgvector for AI Ethical DM

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}===================================================${NC}"
echo -e "${YELLOW}SETTING UP LOCAL POSTGRESQL WITH PGVECTOR${NC}"
echo -e "${BLUE}===================================================${NC}"

# Define database constants
POSTGRES_PORT="5432"
POSTGRES_USER="postgres"
POSTGRES_PASSWORD="PASS"
POSTGRES_DB="ai_ethical_dm"

# Step 1: Check if PostgreSQL service is running
echo -e "${YELLOW}Checking if PostgreSQL service is running...${NC}"
if sudo service postgresql status &> /dev/null; then
    echo -e "${GREEN}PostgreSQL service is running${NC}"
else
    echo -e "${YELLOW}PostgreSQL service is not running. Starting it...${NC}"
    sudo service postgresql start
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to start PostgreSQL service. Please check logs.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}PostgreSQL service started successfully${NC}"
fi

# Step 2: Check if pgvector extension is installed
echo -e "${YELLOW}Checking if pgvector extension is installed...${NC}"
PGVECTOR_INSTALLED=$(sudo -u postgres psql -t -c "SELECT COUNT(*) FROM pg_available_extensions WHERE name = 'vector';")

if [[ $PGVECTOR_INSTALLED == *"1"* ]]; then
    echo -e "${GREEN}pgvector extension is installed${NC}"
else
    echo -e "${YELLOW}pgvector extension is not installed. Installing it...${NC}"
    
    # Install pgvector
    echo -e "${YELLOW}Installing pgvector extension...${NC}"
    sudo apt-get update
    sudo apt-get install -y postgresql-server-dev-17 build-essential git
    
    # Clone and build pgvector
    git clone --branch v0.7.0 https://github.com/pgvector/pgvector.git /tmp/pgvector
    cd /tmp/pgvector
    make
    sudo make install
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to install pgvector extension. Please check logs.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}pgvector extension installed successfully${NC}"
fi

# Step 3: Check if database exists, if not create it
echo -e "${YELLOW}Checking if database '${POSTGRES_DB}' exists...${NC}"
DB_EXISTS=$(sudo -u postgres psql -t -c "SELECT COUNT(*) FROM pg_database WHERE datname = '${POSTGRES_DB}';")

if [[ $DB_EXISTS == *"1"* ]]; then
    echo -e "${GREEN}Database '${POSTGRES_DB}' already exists${NC}"
else
    echo -e "${YELLOW}Creating database '${POSTGRES_DB}'...${NC}"
    sudo -u postgres psql -c "CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};"
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create database. Please check logs.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}Database '${POSTGRES_DB}' created successfully${NC}"
fi

# Step 4: Enable pgvector extension on the database
echo -e "${YELLOW}Enabling pgvector extension on database '${POSTGRES_DB}'...${NC}"
sudo -u postgres psql -d ${POSTGRES_DB} -c "CREATE EXTENSION IF NOT EXISTS vector;"

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to enable pgvector extension. Please check logs.${NC}"
    exit 1
fi

echo -e "${GREEN}pgvector extension enabled successfully${NC}"

# Step 5: Update or create .env file with local PostgreSQL connection
if [ -f ".env" ]; then
    echo -e "${YELLOW}Updating DATABASE_URL in .env file...${NC}"
    sed -i "s|DATABASE_URL=.*|DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${POSTGRES_PORT}/${POSTGRES_DB}|g" .env
    
    # Ensure other necessary settings
    if ! grep -q "USE_MOCK_GUIDELINE_RESPONSES" .env; then
        echo "USE_MOCK_GUIDELINE_RESPONSES=true" >> .env
    fi
else
    echo -e "${YELLOW}Creating .env file...${NC}"
    cp .env.example .env 2>/dev/null || echo "DATABASE_URL=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${POSTGRES_PORT}/${POSTGRES_DB}" > .env
    echo "USE_MOCK_GUIDELINE_RESPONSES=true" >> .env
    echo -e "${GREEN}Created .env file${NC}"
fi

# Step 6: Set up password for PostgreSQL user
echo -e "${YELLOW}Setting up password for PostgreSQL user...${NC}"
sudo -u postgres psql -c "ALTER USER ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';"

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to set password for PostgreSQL user. Please check logs.${NC}"
    exit 1
fi

echo -e "${GREEN}Password set successfully${NC}"

# Step 7: Verify database connection
echo -e "${BLUE}Checking database connection...${NC}"
PGPASSWORD=${POSTGRES_PASSWORD} psql -h localhost -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c "\conninfo"

if [ $? -ne 0 ]; then
    echo -e "${RED}Database connection failed. Please check connection parameters.${NC}"
    exit 1
fi

echo -e "${GREEN}Database connection successful!${NC}"

# Step 8: Verify pgvector extension is enabled in the database
echo -e "${BLUE}Verifying pgvector extension is enabled...${NC}"
PGVECTOR_ENABLED=$(PGPASSWORD=${POSTGRES_PASSWORD} psql -h localhost -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d ${POSTGRES_DB} -t -c "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector';")

if [[ $PGVECTOR_ENABLED == *"1"* ]]; then
    echo -e "${GREEN}pgvector extension is properly enabled on database '${POSTGRES_DB}'${NC}"
else
    echo -e "${RED}pgvector extension is NOT enabled on database '${POSTGRES_DB}'${NC}"
    echo -e "${YELLOW}Try enabling it manually:${NC}"
    echo -e "PGPASSWORD=${POSTGRES_PASSWORD} psql -h localhost -p ${POSTGRES_PORT} -U ${POSTGRES_USER} -d ${POSTGRES_DB} -c \"CREATE EXTENSION IF NOT EXISTS vector;\""
fi

# Step 9: Create schema if needed
echo -e "${BLUE}Setting up database schema...${NC}"
python scripts/ensure_schema.py

if [ $? -ne 0 ]; then
    echo -e "${RED}Database schema setup failed. See logs above.${NC}"
    echo -e "${YELLOW}You may need to fix the ensure_schema.py script.${NC}"
else
    echo -e "${GREEN}Database schema set up successfully!${NC}"
fi

# Create mock guideline responses directory if needed
MOCK_DIR="./mcp/mock_responses"
if [ ! -d "$MOCK_DIR" ]; then
    echo -e "${BLUE}Creating mock responses directory...${NC}"
    mkdir -p "$MOCK_DIR"
    
    echo -e "${YELLOW}Creating sample mock responses...${NC}"
    # Create a sample mock response for concept extraction
    cat > "$MOCK_DIR/extract_concepts_response.json" << EOF
{
  "concepts": [
    {
      "name": "Responsibility",
      "definition": "The ethical obligation to act in the best interest of others and to fulfill duties.",
      "type": "EthicalPrinciple",
      "related_terms": ["Accountability", "Duty", "Obligation"],
      "examples": ["Engineers have a responsibility to ensure public safety in their designs."]
    },
    {
      "name": "Professional Integrity",
      "definition": "Maintaining high ethical standards and honesty in professional practice.",
      "type": "ProfessionalValue",
      "related_terms": ["Honesty", "Ethics", "Professionalism"],
      "examples": ["Engineers should not falsify test results, even under pressure from management."]
    },
    {
      "name": "Public Safety",
      "definition": "The paramount concern for protecting the public from harm in engineering decisions.",
      "type": "EthicalConcern",
      "related_terms": ["Risk Assessment", "Harm Prevention", "Public Welfare"],
      "examples": ["Engineers must prioritize safety over cost considerations."]
    },
    {
      "name": "Conflict of Interest",
      "definition": "A situation where professional judgment may be compromised by secondary interests.",
      "type": "EthicalIssue",
      "related_terms": ["Bias", "Disclosure", "Impartiality"],
      "examples": ["An engineer should not review work for a company where they hold substantial stock."]
    },
    {
      "name": "Whistle-blowing",
      "definition": "Reporting unethical or illegal activities within an organization to appropriate authorities.",
      "type": "EthicalAction",
      "related_terms": ["Disclosure", "Reporting", "Moral Courage"],
      "examples": ["An engineer may need to report safety violations when internal reporting fails."]
    }
  ]
}
EOF

    # Create a sample triples response
    cat > "$MOCK_DIR/generate_triples_response.json" << EOF
{
  "triples": [
    {
      "subject": "http://example.org/guidelines/concepts/Responsibility",
      "subject_label": "Responsibility",
      "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
      "predicate_label": "is a",
      "object": "http://example.org/ontology/EthicalPrinciple",
      "object_label": "Ethical Principle",
      "confidence": 0.95
    },
    {
      "subject": "http://example.org/guidelines/concepts/Responsibility",
      "subject_label": "Responsibility",
      "predicate": "http://purl.org/dc/elements/1.1/description",
      "predicate_label": "has description",
      "object": "The ethical obligation to act in the best interest of others and to fulfill duties.",
      "confidence": 0.92
    },
    {
      "subject": "http://example.org/guidelines/concepts/Professional_Integrity",
      "subject_label": "Professional Integrity",
      "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
      "predicate_label": "is a",
      "object": "http://example.org/ontology/ProfessionalValue",
      "object_label": "Professional Value",
      "confidence": 0.94
    },
    {
      "subject": "http://example.org/guidelines/concepts/Professional_Integrity",
      "subject_label": "Professional Integrity",
      "predicate": "http://purl.org/dc/elements/1.1/description",
      "predicate_label": "has description",
      "object": "Maintaining high ethical standards and honesty in professional practice.",
      "confidence": 0.91
    },
    {
      "subject": "http://example.org/guidelines/concepts/Public_Safety",
      "subject_label": "Public Safety",
      "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
      "predicate_label": "is a",
      "object": "http://example.org/ontology/EthicalConcern",
      "object_label": "Ethical Concern",
      "confidence": 0.97
    },
    {
      "subject": "http://example.org/guidelines/concepts/Public_Safety",
      "subject_label": "Public Safety",
      "predicate": "http://purl.org/dc/elements/1.1/description",
      "predicate_label": "has description",
      "object": "The paramount concern for protecting the public from harm in engineering decisions.",
      "confidence": 0.93
    },
    {
      "subject": "http://example.org/guidelines/concepts/Conflict_of_Interest",
      "subject_label": "Conflict of Interest",
      "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
      "predicate_label": "is a",
      "object": "http://example.org/ontology/EthicalIssue",
      "object_label": "Ethical Issue",
      "confidence": 0.89
    },
    {
      "subject": "http://example.org/guidelines/concepts/Whistle-blowing",
      "subject_label": "Whistle-blowing",
      "predicate": "http://www.w3.org/1999/02/22-rdf-syntax-ns#type",
      "predicate_label": "is a",
      "object": "http://example.org/ontology/EthicalAction",
      "object_label": "Ethical Action",
      "confidence": 0.92
    }
  ],
  "triple_count": 8
}
EOF
    echo -e "${GREEN}Created sample mock responses${NC}"
fi

echo -e "${BLUE}===================================================${NC}"
echo -e "${GREEN}LOCAL POSTGRESQL WITH PGVECTOR SETUP COMPLETE${NC}"
echo -e "${BLUE}===================================================${NC}"
echo -e "${GREEN}Database connection: postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost:${POSTGRES_PORT}/${POSTGRES_DB}${NC}"
echo -e "${BLUE}===================================================${NC}"
