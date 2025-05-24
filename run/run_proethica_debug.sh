#!/bin/bash
# ProEthica Debug Launcher
# Comprehensive script to start the entire ProEthica application with proper setup
#
# Usage:
# ./run_proethica_debug.sh           # Run full setup and start the app
# ./run_proethica_debug.sh setup     # Run only setup (for VSCode preLaunchTask)

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}==================================================${NC}"
echo -e "${YELLOW}ProEthica Debug Launcher - Starting All Components${NC}"
echo -e "${BLUE}==================================================${NC}"

# Setup environment 
export ENVIRONMENT="development"
export FLASK_DEBUG=1
export PYTHONUNBUFFERED=1
export USE_MOCK_GUIDELINE_RESPONSES=true
export MCP_DEBUG=true
export MCP_SERVER_URL="http://localhost:5001"

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env file...${NC}"
    echo "ENVIRONMENT=development" > .env
    echo "DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm" >> .env
    echo "MCP_SERVER_URL=http://localhost:5001" >> .env
    echo "USE_MOCK_GUIDELINE_RESPONSES=true" >> .env
    echo "MCP_DEBUG=true" >> .env
fi

# Check if Docker is installed
echo -e "${BLUE}Checking if Docker is installed...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker is not installed. This script requires Docker to run PostgreSQL.${NC}"
    exit 1
fi

# Check if Docker service is running
echo -e "${BLUE}Checking if Docker service is running...${NC}"
if ! docker info &> /dev/null; then
    echo -e "${RED}Docker service is not running. Please start Docker and try again.${NC}"
    exit 1
fi

# Check if PostgreSQL container is running
echo -e "${BLUE}Checking if PostgreSQL container is running...${NC}"
if docker ps | grep -q proethica-postgres; then
    echo -e "${GREEN}PostgreSQL container is already running${NC}"
else
    echo -e "${YELLOW}PostgreSQL container is not running. Starting it...${NC}"
    
    # Check if container exists but is stopped
    if docker ps -a | grep -q proethica-postgres; then
        echo -e "${YELLOW}Found stopped container. Starting it...${NC}"
        docker start proethica-postgres
    else
        echo -e "${YELLOW}Container not found. Starting new container using docker-compose...${NC}"
        docker-compose up -d postgres
    fi
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to start PostgreSQL container. Please check Docker logs.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}PostgreSQL container started successfully${NC}"
    
    # Wait for PostgreSQL to be ready
    echo -e "${YELLOW}Waiting for PostgreSQL to be ready...${NC}"
    sleep 5
fi

# Update database URL in .env to use Docker PostgreSQL
echo -e "${BLUE}Updating DATABASE_URL in .env...${NC}"
sed -i 's|DATABASE_URL=.*|DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm|g' .env

# Check if we can connect to the database
echo -e "${BLUE}Testing database connection...${NC}"
PGPASSWORD=PASS psql -h localhost -p 5433 -U postgres -d ai_ethical_dm -c "SELECT 1" &> /dev/null

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to connect to PostgreSQL. Please check if container is running properly.${NC}"
    docker logs proethica-postgres
    echo -e "${YELLOW}Continuing anyway, but application may not work correctly.${NC}"
else
    echo -e "${GREEN}Successfully connected to PostgreSQL database${NC}"
    
    # Check if pgvector extension is enabled
    echo -e "${BLUE}Checking if pgvector extension is enabled...${NC}"
    PGVECTOR_ENABLED=$(PGPASSWORD=PASS psql -h localhost -p 5433 -U postgres -d ai_ethical_dm -t -c "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector';")
    
    if [[ $PGVECTOR_ENABLED == *"1"* ]]; then
        echo -e "${GREEN}pgvector extension is already enabled${NC}"
    else
        echo -e "${YELLOW}Enabling pgvector extension...${NC}"
        PGPASSWORD=PASS psql -h localhost -p 5433 -U postgres -d ai_ethical_dm -c "CREATE EXTENSION IF NOT EXISTS vector;"
        
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to enable pgvector extension. This container should have it pre-installed.${NC}"
            echo -e "${YELLOW}Continuing anyway, but vector operations may not work.${NC}"
        else
            echo -e "${GREEN}pgvector extension enabled successfully${NC}"
        fi
    fi
fi

# Create necessary mock response directories and files
echo -e "${BLUE}Setting up mock responses...${NC}"
MOCK_DIR="./mcp/mock_responses"
if [ ! -d "$MOCK_DIR" ]; then
    echo -e "${YELLOW}Creating mock responses directory...${NC}"
    mkdir -p "$MOCK_DIR"
    
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
    }
  ]
}
EOF

    # Create sample triple generation response
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
    }
  ],
  "triple_count": 3
}
EOF
    echo -e "${GREEN}Created mock response files${NC}"
fi

# Ensure tables are created
echo -e "${BLUE}Creating necessary database tables...${NC}"

# Create guidelines table script
if [ -f "create_guidelines_table.sql" ]; then
    echo -e "${YELLOW}Creating guidelines table...${NC}"
    PGPASSWORD=PASS psql -h localhost -p 5433 -U postgres -d ai_ethical_dm -f create_guidelines_table.sql
    
    if [ $? -ne 0 ]; then
        echo -e "${YELLOW}Guidelines table may already exist or creation failed. Continuing...${NC}"
    else
        echo -e "${GREEN}Guidelines table created successfully${NC}"
    fi
fi

# Make sure scripts/ensure_schema.py is called correctly
if [ -f "./scripts/ensure_schema.py" ]; then
    echo -e "${YELLOW}Running schema verification...${NC}"
    
    # Patch ensure_schema.py if needed (to fix missing engine parameter)
    if grep -q "ensure_guidelines_table()" "./scripts/ensure_schema.py"; then
        sed -i 's/ensure_guidelines_table()/ensure_guidelines_table(engine)/g' "./scripts/ensure_schema.py"
        echo -e "${YELLOW}Patched ensure_schema.py to include engine parameter${NC}"
    fi
    
    # Run the script
    python ./scripts/ensure_schema.py
    
    if [ $? -ne 0 ]; then
        echo -e "${YELLOW}Schema verification encountered errors. The application may not work correctly.${NC}"
    else
        echo -e "${GREEN}Schema verification completed successfully${NC}"
    fi
else
    echo -e "${YELLOW}Schema verification script not found. Skipping...${NC}"
fi

# Create logs directory
echo -e "${BLUE}Creating logs directory...${NC}"
mkdir -p logs

# Kill any existing MCP server
echo -e "${BLUE}Checking for existing MCP processes...${NC}"
pkill -f "python mcp/run_enhanced_mcp_server_with_guidelines.py" 2>/dev/null
echo -e "${GREEN}Killed any existing MCP processes${NC}"

# Start MCP server
echo -e "${BLUE}Starting MCP server...${NC}"
python mcp/run_enhanced_mcp_server_with_guidelines.py > logs/mcp_server.log 2>&1 &
MCP_PID=$!
echo -e "${GREEN}MCP server started with PID: $MCP_PID${NC}"

# Give it time to start
echo -e "${YELLOW}Waiting for MCP server to initialize...${NC}"
sleep 5

# Check if MCP server is running
if ps -p $MCP_PID > /dev/null; then
    echo -e "${GREEN}MCP server is running.${NC}"
else
    echo -e "${RED}MCP server failed to start. Check logs/mcp_server.log for details.${NC}"
    echo -e "${YELLOW}Continuing anyway, but application may not work correctly.${NC}"
fi

# Check if we're in setup-only mode
if [ "$1" = "setup" ]; then
    echo -e "${BLUE}==================================================${NC}"
    echo -e "${GREEN}Setup complete. Debug environment ready.${NC}"
    echo -e "${BLUE}==================================================${NC}"
    
    # Create debug environment variables file for VSCode
    mkdir -p .vscode
    echo "DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm" > .vscode/debug_env_vars
    echo "MCP_SERVER_URL=http://localhost:5001" >> .vscode/debug_env_vars
    echo "MCP_SERVER_PORT=5001" >> .vscode/debug_env_vars
    echo "MCP_SERVER_ALREADY_RUNNING=true" >> .vscode/debug_env_vars
    echo "USE_MOCK_GUIDELINE_RESPONSES=true" >> .vscode/debug_env_vars
    echo "MCP_DEBUG=true" >> .vscode/debug_env_vars
    echo "FLASK_APP=app/__init__.py" >> .vscode/debug_env_vars
    echo "ENVIRONMENT=development" >> .vscode/debug_env_vars
    
    exit 0
fi

# Start the Flask app
echo -e "${BLUE}==================================================${NC}"
echo -e "${YELLOW}Starting Flask application...${NC}"
echo -e "${BLUE}==================================================${NC}"
echo -e "${GREEN}You can access the application at: http://localhost:3333${NC}"
echo -e "${BLUE}==================================================${NC}"

python run.py --port 3333 --mcp-port 5001
