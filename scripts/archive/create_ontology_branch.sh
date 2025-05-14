#!/bin/bash
# Script to create a new git branch focused on ontology-based case analysis

# Set script to exit on error
set -e

# Define colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Branch names
BASE_BRANCH="realm-integration"
NEW_BRANCH="ontology-case-analysis"

echo -e "${YELLOW}Creating new branch for ontology-based case analysis...${NC}"

# Check if we're in a git repository
if ! git rev-parse --is-inside-work-tree > /dev/null 2>&1; then
    echo -e "${RED}Error: Not in a git repository. Please run this script from the project root.${NC}"
    exit 1
fi

# Fetch the latest changes
echo -e "${YELLOW}Fetching latest changes from remote...${NC}"
git fetch

# Check if the base branch exists
if ! git show-ref --verify --quiet refs/heads/$BASE_BRANCH; then
    # Check if it exists in the remote
    if git show-ref --verify --quiet refs/remotes/origin/$BASE_BRANCH; then
        echo -e "${YELLOW}Base branch '$BASE_BRANCH' exists in remote but not locally. Creating local branch...${NC}"
        git checkout -b $BASE_BRANCH origin/$BASE_BRANCH
    else
        echo -e "${RED}Error: Base branch '$BASE_BRANCH' does not exist. Please check the branch name.${NC}"
        exit 1
    fi
else
    # Switch to the base branch and update it
    echo -e "${YELLOW}Checking out and updating base branch '$BASE_BRANCH'...${NC}"
    git checkout $BASE_BRANCH
    git pull
fi

# Check if the new branch already exists
if git show-ref --verify --quiet refs/heads/$NEW_BRANCH; then
    echo -e "${YELLOW}Branch '$NEW_BRANCH' already exists.${NC}"
    
    # Ask if the user wants to use the existing branch or create a new one with a different name
    read -p "Do you want to switch to the existing branch? (y/n) " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${YELLOW}Switching to existing branch '$NEW_BRANCH'...${NC}"
        git checkout $NEW_BRANCH
        echo -e "${GREEN}Successfully switched to branch '$NEW_BRANCH'.${NC}"
        exit 0
    else
        # Ask for a new branch name
        read -p "Enter a new branch name: " NEW_BRANCH_NAME
        NEW_BRANCH=$NEW_BRANCH_NAME
        
        # Check if the new branch name already exists
        if git show-ref --verify --quiet refs/heads/$NEW_BRANCH; then
            echo -e "${RED}Error: Branch '$NEW_BRANCH' already exists. Please choose a different name.${NC}"
            exit 1
        fi
    fi
fi

# Create the new branch
echo -e "${YELLOW}Creating new branch '$NEW_BRANCH' based on '$BASE_BRANCH'...${NC}"
git checkout -b $NEW_BRANCH

# Add branch description
DESCRIPTION="Branch focused on ontology-based case analysis using McLaren's methodology. This branch implements the extensions needed for analyzing engineering ethics cases using McLaren's operationalization techniques and supporting ontology-based simulation."
git config branch.$NEW_BRANCH.description "$DESCRIPTION"

# Create a commit with the initial documentation
git add docs/ontology_case_analysis_plan.md
git add scripts/verify_proethica_ontology.py
git add app/routes/ontology_routes.py

git commit -m "Initialize ontology case analysis branch

- Added detailed implementation plan for case analysis using McLaren's methodology
- Created verification script for ProEthica and ontology server connectivity
- Added API routes for ontology interactions
- Configured Flask app to use the new ontology API routes"

echo -e "${GREEN}Successfully created and configured branch '$NEW_BRANCH'.${NC}"
echo -e "${YELLOW}Branch description:${NC}"
echo "$DESCRIPTION"
echo
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Implement the basic integration between ProEthica and the unified ontology server"
echo "2. Create database migrations for the enhanced schema"
echo "3. Develop the case analysis components based on McLaren's paper"
echo
echo -e "${GREEN}To push this branch to remote, use:${NC}"
echo "git push -u origin $NEW_BRANCH"
