#!/bin/bash

# Color definitions
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if Git is installed
if ! command -v git &> /dev/null; then
    echo -e "${RED}Error: Git is not installed. Please install Git and try again.${NC}"
    exit 1
fi

# Default branch name if not provided
DEFAULT_BRANCH="ontology-enhancement"

# If a branch name is provided, use it; otherwise use the default
BRANCH_NAME=${1:-$DEFAULT_BRANCH}

echo -e "${BLUE}Creating a new branch focused on ontology features...${NC}"

# Check if we're in a git repository
if ! git rev-parse --is-inside-work-tree &> /dev/null; then
    echo -e "${RED}Error: Not inside a Git repository.${NC}"
    exit 1
fi

# Check if realm-integration branch exists
if ! git show-ref --quiet refs/heads/realm-integration; then
    echo -e "${RED}Error: realm-integration branch does not exist locally.${NC}"
    echo -e "${YELLOW}Checking if it exists remotely...${NC}"
    
    git fetch
    
    if ! git show-ref --quiet refs/remotes/origin/realm-integration; then
        echo -e "${RED}Error: realm-integration branch does not exist remotely either.${NC}"
        exit 1
    else
        echo -e "${YELLOW}Found realm-integration branch remotely. Creating local branch.${NC}"
        git checkout -b realm-integration origin/realm-integration
    fi
fi

# Make sure we're up to date
echo -e "${BLUE}Making sure realm-integration branch is up to date...${NC}"
git checkout realm-integration
git pull

# Create a new branch based on realm-integration
echo -e "${BLUE}Creating new branch ${YELLOW}$BRANCH_NAME${BLUE} based on realm-integration...${NC}"
git checkout -b $BRANCH_NAME

# Create a placeholder file for tracking ontology-focused changes
echo -e "${BLUE}Creating documentation file for ontology features...${NC}"

cat > ONTOLOGY_ENHANCEMENT_README.md << 'EOL'
# Ontology Enhancement Branch

This branch focuses on enhancing the ontology capabilities of ProEthica based on the realm-integration branch.

## Focus Areas

1. **Unified Ontology System**: Integrating and enhancing the ontology capabilities
2. **Enhanced Case Analysis**: Using ontologies for improved case analysis
3. **Temporal Ontology Features**: Adding temporal functionality to the ontology system

## Implementation Details

### Unified Ontology Server

The unified ontology server provides centralized access to ontology data and functionality.
Key features include:
- Standardized API for ontology access
- Dynamic loading of ontology modules
- Query capabilities across multiple ontology sources

### Case Analysis Integration

Case analysis functionality uses ontologies to:
- Extract ethical principles from cases
- Map case elements to ontology concepts
- Provide structured ethical reasoning

## Configuration

The ontology server runs on port 5002 by default to avoid conflicts with other services.
The MCP client has been modified to handle URL formatting issues and properly connect to the ontology server.

## Usage

To start the unified ontology server:
```bash
./start_unified_ontology_server.sh
```

To stop the server:
```bash
./stop_unified_ontology_server.sh
```
EOL

echo -e "${GREEN}Done! You are now on the ${YELLOW}$BRANCH_NAME${GREEN} branch.${NC}"
echo -e "${BLUE}This branch is focused on enhancing the ontology portion of ProEthica.${NC}"
echo -e "${BLUE}Refer to ${YELLOW}ONTOLOGY_ENHANCEMENT_README.md${BLUE} for documentation.${NC}"

# Make the file executable
chmod +x scripts/create_ontology_branch.sh

exit 0
