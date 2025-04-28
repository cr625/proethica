#!/bin/bash
# This script helps to protect sensitive API keys and credentials from being committed to git

set -e  # Exit on error

# ANSI color codes for better readability
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Git Credentials Protection ===${NC}"

# Check if .env is already in .gitignore
if grep -q "^\.env$" .gitignore; then
    echo -e "${GREEN}✓ .env file is already in .gitignore${NC}"
else
    echo -e "${YELLOW}Adding .env to .gitignore...${NC}"
    echo ".env" >> .gitignore
    echo -e "${GREEN}✓ Added .env to .gitignore${NC}"
fi

# Check if we are already ignoring changes to .env
git ls-files -v | grep "^h .env" > /dev/null
ENV_TRACKED=$?
if [ $ENV_TRACKED -eq 0 ]; then
    echo -e "${GREEN}✓ git is already configured to ignore changes to .env${NC}"
else
    echo -e "${YELLOW}Configuring git to ignore changes to existing .env file...${NC}"
    git update-index --assume-unchanged .env
    echo -e "${GREEN}✓ Git will now ignore changes to the existing .env file${NC}"
fi

# Create a template .env.example file if it doesn't exist or is outdated
if [ ! -f .env.example ] || [ "$(grep ANTHROPIC_API_KEY .env.example | grep -v '#')" != "ANTHROPIC_API_KEY=your-anthropic-api-key-here" ]; then
    echo -e "${YELLOW}Creating/updating .env.example template...${NC}"
    # Copy .env to .env.example but replace actual API keys with placeholders
    cat .env | sed 's/ANTHROPIC_API_KEY=.*/ANTHROPIC_API_KEY=your-anthropic-api-key-here/' \
               | sed 's/OPENAI_API_KEY=.*/OPENAI_API_KEY=your-openai-api-key-here/' \
               | sed 's/ZOTERO_API_KEY=.*/ZOTERO_API_KEY=your-zotero-api-key-here/' \
               | sed 's/ZOTERO_USER_ID=.*/ZOTERO_USER_ID=your-zotero-user-id-here/' \
               > .env.example
    echo -e "${GREEN}✓ Created/updated .env.example with safe placeholders${NC}"
fi

echo -e "\n${GREEN}=== Credentials protection complete ===${NC}"
echo -e "Your API keys and credentials in .env are now protected from being committed to git."
echo -e "${YELLOW}IMPORTANT: Any future changes to .env will not be tracked by git.${NC}"
echo -e "To update the .env.example template, run this script again."
echo -e "To resume tracking changes to .env: ${BLUE}git update-index --no-assume-unchanged .env${NC}"
