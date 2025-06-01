#!/bin/bash
# Script to help set up GitHub secrets for CI/CD
# This script generates commands to set GitHub secrets using the GitHub CLI

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}GitHub Secrets Setup Helper${NC}"
echo -e "${BLUE}===========================${NC}"
echo

# Check if gh CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}❌ GitHub CLI (gh) is not installed${NC}"
    echo "Install it from: https://cli.github.com/"
    exit 1
fi

# Check if authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${YELLOW}⚠️  Not authenticated with GitHub${NC}"
    echo "Run: gh auth login"
    exit 1
fi

# Get repository info
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
if [ -z "$REPO" ]; then
    echo -e "${YELLOW}Enter GitHub repository (owner/repo):${NC}"
    read -r REPO
fi

echo -e "${GREEN}Setting up secrets for: $REPO${NC}"
echo

# Function to prompt for secret value
prompt_secret() {
    local name=$1
    local description=$2
    local example=$3
    local current_value=""
    
    # Check if secret already exists
    if gh secret list -R "$REPO" | grep -q "^$name"; then
        echo -e "${YELLOW}ℹ️  Secret $name already exists${NC}"
        echo -n "Do you want to update it? (y/N): "
        read -r update
        if [[ ! "$update" =~ ^[Yy]$ ]]; then
            return
        fi
    fi
    
    echo -e "${BLUE}$name${NC}"
    echo "Description: $description"
    if [ -n "$example" ]; then
        echo "Example: $example"
    fi
    
    # Handle multiline secrets
    if [[ "$name" == "SSH_PRIVATE_KEY" ]]; then
        echo "Enter value (paste SSH private key, press Ctrl+D when done):"
        value=$(cat)
    else
        echo -n "Enter value: "
        read -rs value
        echo
    fi
    
    if [ -n "$value" ]; then
        echo "$value" | gh secret set "$name" -R "$REPO" -f -
        echo -e "${GREEN}✅ Set $name${NC}"
    else
        echo -e "${YELLOW}⚠️  Skipped $name (no value provided)${NC}"
    fi
    echo
}

# Required secrets for deployment
echo -e "${YELLOW}=== Required Secrets for Deployment ===${NC}"
echo

prompt_secret "SSH_PRIVATE_KEY" \
    "SSH private key for server access" \
    "-----BEGIN OPENSSH PRIVATE KEY-----..."

prompt_secret "SSH_HOST" \
    "Server hostname" \
    "proethica.org"

prompt_secret "SSH_USER" \
    "SSH username" \
    "chris"

prompt_secret "ANTHROPIC_API_KEY" \
    "Anthropic API key for Claude" \
    "sk-ant-..."

prompt_secret "MCP_AUTH_TOKEN" \
    "Authentication token for MCP server (generate a secure token)" \
    "$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

prompt_secret "DATABASE_URL" \
    "PostgreSQL connection string" \
    "postgresql://user:password@localhost:5432/dbname"

# Optional secrets
echo -e "${YELLOW}=== Optional Secrets ===${NC}"
echo

echo -n "Set up optional secrets? (y/N): "
read -r setup_optional

if [[ "$setup_optional" =~ ^[Yy]$ ]]; then
    prompt_secret "MCP_URL" \
        "MCP server URL for monitoring" \
        "https://mcp.proethica.org"
    
    prompt_secret "SLACK_WEBHOOK" \
        "Slack webhook URL for notifications" \
        "https://hooks.slack.com/services/..."
    
    # Flask/App secrets
    echo -e "${YELLOW}=== Flask Application Secrets ===${NC}"
    echo
    
    prompt_secret "FLASK_APP" \
        "Flask application entry point" \
        "run.py"
    
    prompt_secret "FLASK_ENV" \
        "Flask environment" \
        "production"
    
    prompt_secret "SECRET_KEY" \
        "Flask secret key (generate a secure key)" \
        "$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
    
    prompt_secret "OPENAI_API_KEY" \
        "OpenAI API key" \
        "sk-..."
    
    # Claude model configuration
    echo -e "${YELLOW}=== Claude Model Configuration ===${NC}"
    echo
    
    prompt_secret "CLAUDE_DEFAULT_MODEL" \
        "Default Claude model" \
        "claude-3-sonnet-20240229"
    
    prompt_secret "CLAUDE_FAST_MODEL" \
        "Fast Claude model for quick responses" \
        "claude-3-haiku-20240307"
    
    prompt_secret "CLAUDE_POWERFUL_MODEL" \
        "Powerful Claude model for complex tasks" \
        "claude-3-opus-20240229"
fi

# Verify secrets
echo -e "${YELLOW}=== Verification ===${NC}"
echo "Current secrets in $REPO:"
gh secret list -R "$REPO"

echo
echo -e "${GREEN}✅ Secret setup complete!${NC}"
echo
echo "Next steps:"
echo "1. Verify all required secrets are set"
echo "2. Test deployment with: gh workflow run deploy-mcp.yml"
echo "3. Check monitoring with: gh workflow run monitor-mcp.yml"
echo
echo "To manually set a secret later:"
echo "  echo 'value' | gh secret set SECRET_NAME -R $REPO -f -"
echo
echo "To generate secure tokens:"
echo "  python3 -c 'import secrets; print(secrets.token_urlsafe(32))'"