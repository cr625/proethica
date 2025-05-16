#!/bin/bash
# Combined debug script for testing guideline concept extraction and saving
# This script sets up a debug environment that includes:
# 1. PostgreSQL with pgvector properly set up
# 2. Database schema verification and fixing
# 3. Flask app running with debug mode
# 4. MCP server with guideline analysis module
# 5. Mock Claude responses for testing
#
# The script can be run in two modes:
# - Full mode: Sets up everything and starts Flask and MCP server
# - Setup-only mode: Only sets up PostgreSQL (for VSCode integration)
#   Enable this by setting SETUP_ONLY=true before running

# Don't exit on error - we want to handle errors gracefully
# set -e

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Print banner
echo -e "${BLUE}=================================${NC}"
echo -e "${BLUE}= Guideline Concept Debug Setup =${NC}"
echo -e "${BLUE}=================================${NC}"

# Check if backup exists
if [ ! -d "./backups" ]; then
    echo -e "${RED}Error: backups directory not found${NC}"
    echo "Please make sure you're in the project root directory"
    exit 1
fi

# Define PostgreSQL container variables for Codespaces
POSTGRES_CONTAINER="postgres17-pgvector-codespace"
POSTGRES_VERSION="17"
POSTGRES_PORT="5433"
POSTGRES_USER="postgres"
POSTGRES_PASSWORD="PASS"
POSTGRES_DB="ai_ethical_dm"

# Setup the PostgreSQL container with pgvector
echo -e "${BLUE}Setting up PostgreSQL container with pgvector...${NC}"

# Stop and remove any existing containers with the same name
echo -e "${YELLOW}Stopping and removing any existing PostgreSQL containers...${NC}"
docker stop $POSTGRES_CONTAINER 2>/dev/null || true
docker rm -f $POSTGRES_CONTAINER 2>/dev/null || true
echo -e "${GREEN}Removed any existing containers.${NC}"

# Clean up any stale Docker networks/volumes
echo -e "${YELLOW}Cleaning up Docker resources...${NC}"
docker network prune -f >/dev/null 2>&1
docker volume prune -f >/dev/null 2>&1

# Build and start fresh container
echo -e "${YELLOW}Building PostgreSQL image with pgvector...${NC}"
if [ -f "./postgres.Dockerfile" ]; then
    docker build -t postgres-pgvector:$POSTGRES_VERSION -f postgres.Dockerfile . || {
        echo -e "${RED}Failed to build Docker image. Trying with pgvector from Docker Hub instead.${NC}"
        docker run --name $POSTGRES_CONTAINER \
            -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
            -e POSTGRES_USER=$POSTGRES_USER \
            -e POSTGRES_DB=$POSTGRES_DB \
            -p $POSTGRES_PORT:5432 \
            -d pgvector/pgvector:pg$POSTGRES_VERSION || {
                echo -e "${RED}Failed to start container. Please check Docker logs.${NC}"
                exit 1
            }
    }
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Image built successfully. Starting container...${NC}"
        docker run --name $POSTGRES_CONTAINER \
            -e POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
            -e POSTGRES_USER=$POSTGRES_USER \
            -e POSTGRES_DB=$POSTGRES_DB \
            -p $POSTGRES_PORT:5432 \
            -d postgres-pgvector:$POSTGRES_VERSION
    fi
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

# Wait for container to initialize
echo -e "${YELLOW}Waiting for PostgreSQL to initialize (15 seconds)...${NC}"
sleep 15

# Verify container is running
if [ ! "$(docker ps -q -f name=$POSTGRES_CONTAINER)" ]; then
    echo -e "${RED}PostgreSQL container failed to start. Please check Docker logs:${NC}"
    docker logs $POSTGRES_CONTAINER
    exit 1
fi

# Initialize pgvector extension
echo -e "${YELLOW}Initializing pgvector extension...${NC}"
docker exec -i $POSTGRES_CONTAINER psql -U $POSTGRES_USER -d $POSTGRES_DB -c 'CREATE EXTENSION IF NOT EXISTS pgvector;' || {
    echo -e "${RED}Failed to initialize pgvector extension. Trying again after 5 seconds...${NC}"
    sleep 5
    docker exec -i $POSTGRES_CONTAINER psql -U $POSTGRES_USER -d $POSTGRES_DB -c 'CREATE EXTENSION IF NOT EXISTS pgvector;'
}

# Update or create .env file
if [ -f ".env" ]; then
    echo -e "${YELLOW}Updating DATABASE_URL in .env file...${NC}"
    sed -i "s|DATABASE_URL=.*|DATABASE_URL=postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:$POSTGRES_PORT/$POSTGRES_DB|g" .env
    
    # Ensure other necessary settings
    if ! grep -q "USE_MOCK_GUIDELINE_RESPONSES" .env; then
        echo "USE_MOCK_GUIDELINE_RESPONSES=true" >> .env
    fi
else
    echo -e "${YELLOW}Creating .env file...${NC}"
    cp .env.example .env 2>/dev/null || echo "DATABASE_URL=postgresql://$POSTGRES_USER:$POSTGRES_PASSWORD@localhost:$POSTGRES_PORT/$POSTGRES_DB" > .env
    echo "USE_MOCK_GUIDELINE_RESPONSES=true" >> .env
    echo -e "${GREEN}Created .env file${NC}"
fi

# Source updated environment variables
source .env

# Verify database connection
echo -e "${BLUE}Checking database connection...${NC}"
if ! PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "\conninfo"; then
    echo -e "${RED}Database connection failed. Please check container status and connection parameters.${NC}"
    echo -e "${YELLOW}Container status:${NC}"
    docker ps -a -f name=$POSTGRES_CONTAINER
    exit 1
fi
echo -e "${GREEN}Database connection successful!${NC}"

# Ensure database schema has necessary tables and columns
echo -e "${BLUE}Verifying and updating database schema...${NC}"
python scripts/ensure_schema.py

if [ $? -ne 0 ]; then
    echo -e "${RED}Database schema verification failed. See logs above.${NC}"
    echo -e "${YELLOW}Continuing anyway, but you may encounter errors...${NC}"
else
    echo -e "${GREEN}Database schema verified and updated successfully!${NC}"
fi

# Verify guideline concepts SQL table status
echo -e "${BLUE}Checking guidelines and entity_triples tables...${NC}"
PGPASSWORD=$POSTGRES_PASSWORD psql -h localhost -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -f verify_guideline_concepts.sql

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

# Set up environment for mock responses
export USE_MOCK_RESPONSES=true
export MOCK_RESPONSES_DIR="$MOCK_DIR"

# Check for setup-only mode
if [ "$SETUP_ONLY" = "true" ]; then
    echo -e "${BLUE}Running in setup-only mode (PostgreSQL configuration only)${NC}"
    
    # Exit with success after setup is complete
    echo -e "${GREEN}PostgreSQL setup complete! Exiting setup-only mode.${NC}"
    exit 0
else
    # Start the MCP server with guideline analysis in a new terminal
    echo -e "${BLUE}Starting MCP server with guideline analysis module...${NC}"
    gnome-terminal -- bash -c "source .env && echo -e '${GREEN}Starting MCP server...${NC}' && python mcp/run_enhanced_mcp_server_with_guidelines.py; read -p 'Press Enter to close...'"

    # Wait for MCP server to start
    echo -e "${YELLOW}Waiting for MCP server to initialize (5 seconds)...${NC}"
    sleep 5

    # Start the Flask app in debug mode
    echo -e "${BLUE}Starting Flask app in debug mode...${NC}"
    gnome-terminal -- bash -c "source .env && echo -e '${GREEN}Starting Flask app...${NC}' && python -m flask run --debug --port 5000; read -p 'Press Enter to close...'"

    # Wait for Flask app to start
    echo -e "${YELLOW}Waiting for Flask app to initialize (3 seconds)...${NC}"
    sleep 3

    # Open browser to the guidelines page
    echo -e "${BLUE}Opening browser to view guidelines list...${NC}"
    python -c "import webbrowser; webbrowser.open('http://localhost:5000/worlds')"

    echo -e "${GREEN}Debug environment is ready!${NC}"
    echo 
    echo -e "${YELLOW}To test the guideline concept extraction:${NC}"
    echo "1. Create a new world if needed"
    echo "2. Add a guideline document to the world"
    echo "3. Click on 'Extract Concepts' for the guideline"
    echo "4. Review and select concepts to save"
    echo "5. Click 'Save Selected Concepts'"
    echo 
    echo -e "${BLUE}To verify saved concepts:${NC}"
    echo "Run: python query_guideline_concepts.py"
    echo
    echo -e "${YELLOW}Press Ctrl+C to stop this script when done testing${NC}"

    # Keep script running
    while true; do
      sleep 1
    done
fi
