#!/bin/bash
# Script to create a new branch focused on ontology functionality based on the realm-integration branch

# Set colored output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Creating a new branch focused on ontology functionality${NC}"
echo -e "${BLUE}Based on the realm-integration branch${NC}"

# Check if we're in the right directory
if [ ! -d "mcp" ] || [ ! -d "app" ] || [ ! -d "docs" ]; then
    echo -e "${RED}Error: This doesn't appear to be the project root directory.${NC}"
    echo -e "${YELLOW}Please run this script from the project root directory.${NC}"
    exit 1
fi

# Ensure we're on the realm-integration branch first
echo -e "${BLUE}Checking out realm-integration branch...${NC}"
git checkout realm-integration

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to checkout realm-integration branch.${NC}"
    echo -e "${YELLOW}Make sure the branch exists and there are no uncommitted changes.${NC}"
    exit 1
fi

# Update the branch to latest
echo -e "${BLUE}Pulling latest changes...${NC}"
git pull

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to pull latest changes.${NC}"
    echo -e "${YELLOW}Resolve any conflicts and try again.${NC}"
    exit 1
fi

# Set the branch name
DEFAULT_BRANCH="ontology-enhancement"
NEW_BRANCH=${1:-$DEFAULT_BRANCH}

# Check if branch already exists
BRANCH_EXISTS=$(git branch --list $NEW_BRANCH)
if [ ! -z "$BRANCH_EXISTS" ]; then
    echo -e "${YELLOW}Branch '$NEW_BRANCH' already exists.${NC}"
    
    read -p "Do you want to delete and recreate this branch? (y/n) " -n 1 -r REPLY
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}Deleting existing branch...${NC}"
        git branch -D $NEW_BRANCH
        
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to delete existing branch.${NC}"
            exit 1
        fi
        
        echo -e "${GREEN}Successfully deleted existing branch.${NC}"
    else
        echo -e "${YELLOW}Please choose a different branch name:${NC}"
        read -p "Enter new branch name: " NEW_BRANCH_NAME
        
        if [ -z "$NEW_BRANCH_NAME" ]; then
            echo -e "${RED}No branch name provided. Exiting.${NC}"
            exit 1
        fi
        
        NEW_BRANCH=$NEW_BRANCH_NAME
    fi
fi

# Create the new branch
echo -e "${BLUE}Creating new branch: ${NEW_BRANCH}...${NC}"
git checkout -b $NEW_BRANCH

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to create new branch.${NC}"
    exit 1
fi

echo -e "${GREEN}Successfully created new branch: ${NEW_BRANCH}${NC}"
echo -e "${YELLOW}Current branch is now: ${NEW_BRANCH}${NC}"

# Add the new files we created
echo -e "${BLUE}Adding new files to git...${NC}"

# Add our modular MCP server implementation
git add mcp/modules/__init__.py
git add mcp/modules/base_module.py
git add mcp/modules/query_module.py
git add mcp/modules/case_analysis_module.py
git add mcp/unified_ontology_server.py
git add run_unified_mcp_server.py

# Add documentation files
git add docs/unified_ontology_server.md
git add docs/case_analysis_using_ontology.md

echo -e "${GREEN}Files added to git${NC}"

# Create initial commit
echo -e "${BLUE}Creating initial commit...${NC}"
git commit -m "Initial implementation of unified ontology system with modular architecture"

if [ $? -ne 0 ]; then
    echo -e "${RED}Failed to create initial commit.${NC}"
    echo -e "${YELLOW}You may need to add the files manually.${NC}"
    exit 1
fi

echo -e "${GREEN}Branch created and initial commit made successfully${NC}"
echo -e "${YELLOW}====================================================${NC}"
echo -e "${YELLOW}Next steps:${NC}"
echo -e "${YELLOW}- Implement the relationship_module.py and temporal_module.py${NC}"
echo -e "${YELLOW}- Update the unified_ontology_server.py to load all modules${NC}"
echo -e "${YELLOW}- Create integration tests${NC}"
echo -e "${YELLOW}- Create a script to start the unified ontology server${NC}"
echo -e "${YELLOW}====================================================${NC}"
