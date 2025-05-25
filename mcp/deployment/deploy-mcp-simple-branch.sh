#!/bin/bash
# MCP Server Deployment Script for Simple Branch
# This script handles the current reality: deploying from 'simple' branch to home directory

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-production}
BRANCH="simple"  # Current active branch
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${BLUE}🚀 ProEthica MCP Server Deployment (Simple Branch)${NC}"
echo -e "${BLUE}=================================================${NC}"
echo -e "${YELLOW}Environment: $ENVIRONMENT${NC}"
echo -e "${YELLOW}Branch: $BRANCH${NC}"
echo

# Environment-specific configuration
case $ENVIRONMENT in
    production)
        SSH_HOST="proethica.org"
        SSH_USER="chris"
        MCP_PORT="5002"
        DEPLOY_BASE="/home/chris/proethica"  # Home directory deployment
        ;;
    *)
        echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
        echo "Usage: $0 [production]"
        exit 1
        ;;
esac

# Check SSH connection
echo -e "${YELLOW}🔗 Testing SSH connection...${NC}"
if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "$SSH_USER@$SSH_HOST" exit 2>/dev/null; then
    echo -e "${RED}❌ Cannot connect to $SSH_HOST${NC}"
    exit 1
fi
echo -e "${GREEN}✅ SSH connection successful${NC}"

# Check current branch on server
echo -e "${YELLOW}🌿 Checking server branch status...${NC}"
CURRENT_SERVER_BRANCH=$(ssh "$SSH_USER@$SSH_HOST" "cd $DEPLOY_BASE/ai-ethical-dm && git branch --show-current")
echo -e "${BLUE}Server is on branch: $CURRENT_SERVER_BRANCH${NC}"

if [[ "$CURRENT_SERVER_BRANCH" != "$BRANCH" ]]; then
    echo -e "${YELLOW}⚠️  Warning: Server is on '$CURRENT_SERVER_BRANCH', switching to '$BRANCH'${NC}"
fi

# Validate local files
echo -e "${YELLOW}🔍 Validating local MCP server files...${NC}"
cd "$PROJECT_ROOT"

if [[ ! -f "mcp/enhanced_ontology_server_with_guidelines.py" ]]; then
    echo -e "${RED}❌ MCP server file not found${NC}"
    exit 1
fi

# Create deployment package
echo -e "${YELLOW}📦 Creating deployment package...${NC}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TEMP_DIR="/tmp/mcp_deploy_$TIMESTAMP"
mkdir -p "$TEMP_DIR"

# Copy MCP files
cp -r mcp/* "$TEMP_DIR/"
cp requirements-mcp.txt "$TEMP_DIR/" 2>/dev/null || echo "Note: requirements-mcp.txt not found, using main requirements"

# Create deployment info file
cat > "$TEMP_DIR/deployment_info.txt" << EOF
Deployment Information
=====================
Timestamp: $TIMESTAMP
Branch: $BRANCH
Environment: $ENVIRONMENT
Deployed from: $(hostname)
Deployed by: $(whoami)
Git commit: $(git rev-parse HEAD)
Git branch: $(git branch --show-current)
EOF

# Create archive
cd /tmp
tar -czf "mcp_deploy_$TIMESTAMP.tar.gz" "mcp_deploy_$TIMESTAMP"
echo -e "${GREEN}✅ Deployment package created${NC}"

# Deploy to server
echo -e "${YELLOW}📤 Deploying to $SSH_HOST...${NC}"

ssh "$SSH_USER@$SSH_HOST" << EOF
set -e

echo -e "${YELLOW}🏗️ Preparing deployment environment...${NC}"

# Configuration
DEPLOY_BASE="$DEPLOY_BASE"
REPO_DIR="\$DEPLOY_BASE/ai-ethical-dm"
MCP_DIR="\$DEPLOY_BASE/mcp-server"
RELEASE_DIR="\$MCP_DIR/releases/$TIMESTAMP"

# Update repository to correct branch
echo -e "${YELLOW}📥 Updating repository to $BRANCH branch...${NC}"
cd "\$REPO_DIR"
git fetch origin
git checkout "$BRANCH" || git checkout -b "$BRANCH" "origin/$BRANCH"
git pull origin "$BRANCH"

# Show current commit for verification
echo -e "${BLUE}Current commit: \$(git log -1 --oneline)${NC}"

# Create directory structure
mkdir -p "\$MCP_DIR"/{current,releases,shared,logs,config}
mkdir -p "\$RELEASE_DIR"

echo -e "${GREEN}✅ Created release directory: \$RELEASE_DIR${NC}"
EOF

# Transfer deployment package
echo -e "${YELLOW}📤 Transferring files...${NC}"
scp "/tmp/mcp_deploy_$TIMESTAMP.tar.gz" "$SSH_USER@$SSH_HOST:/tmp/"

# Continue deployment on server
ssh "$SSH_USER@$SSH_HOST" << 'EOF'
set -e

# Extract deployment package
cd /tmp
tar -xzf "mcp_deploy_'$TIMESTAMP'.tar.gz"
cp -r "mcp_deploy_'$TIMESTAMP'"/* "'$DEPLOY_BASE'/mcp-server/releases/'$TIMESTAMP'/"
rm -rf "mcp_deploy_'$TIMESTAMP'" "mcp_deploy_'$TIMESTAMP'.tar.gz"

# Set up deployment directory
cd "'$DEPLOY_BASE'/mcp-server/releases/'$TIMESTAMP'"

# Copy files from repository (ensures we have latest from simple branch)
echo -e "'$YELLOW'📋 Copying files from simple branch...'$NC'"
cp -r "'$DEPLOY_BASE'/ai-ethical-dm/mcp/"* .
cp "'$DEPLOY_BASE'/ai-ethical-dm/requirements.txt" . 2>/dev/null || true
cp "'$DEPLOY_BASE'/ai-ethical-dm/requirements-mcp.txt" . 2>/dev/null || true

# Set up Python environment
echo -e "'$YELLOW'🐍 Setting up Python environment...'$NC'"
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip

# Install requirements (try MCP-specific first, fallback to main)
if [[ -f "requirements-mcp.txt" ]]; then
    echo "Installing from requirements-mcp.txt"
    pip install -r requirements-mcp.txt
elif [[ -f "requirements.txt" ]]; then
    echo "Installing from requirements.txt"
    pip install -r requirements.txt
else
    echo -e "'$RED'❌ No requirements file found!'$NC'"
    exit 1
fi

# Create/update environment configuration
echo -e "'$YELLOW'⚙️ Setting up environment configuration...'$NC'"

# Copy existing .env if it exists
if [[ -f "'$DEPLOY_BASE'/mcp-server/current/.env" ]]; then
    cp "'$DEPLOY_BASE'/mcp-server/current/.env" .env
    echo "Copied existing .env file"
else
    # Create basic .env template
    cat > .env << 'ENVEOF'
# MCP Server Configuration
MCP_SERVER_PORT='$MCP_PORT'
USE_MOCK_GUIDELINE_RESPONSES=false
DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm
ENVIRONMENT='$ENVIRONMENT'

# Add your API keys here:
# ANTHROPIC_API_KEY=your-key-here
# MCP_AUTH_TOKEN=your-token-here
ENVEOF
    echo -e "'$YELLOW'⚠️  Created new .env template - please add API keys'$NC'"
fi

# Test startup (with timeout)
echo -e "'$YELLOW'🧪 Testing MCP server startup...'$NC'"
source venv/bin/activate
export PYTHONPATH="'$DEPLOY_BASE'/ai-ethical-dm:$PYTHONPATH"

# Try test mode if available, otherwise just import test
if python -c "import sys; sys.path.insert(0, '.'); from enhanced_ontology_server_with_guidelines import *" 2>/dev/null; then
    echo -e "'$GREEN'✅ MCP server import test passed'$NC'"
else
    echo -e "'$RED'❌ MCP server import test failed'$NC'"
    exit 1
fi

# Stop existing MCP server
echo -e "'$YELLOW'⏹️ Stopping existing MCP server...'$NC'"
pkill -f "enhanced_ontology_server_with_guidelines.py" || echo "No existing server found"
sleep 3

# Update current symlink
ln -sfn "'$DEPLOY_BASE'/mcp-server/releases/'$TIMESTAMP'" "'$DEPLOY_BASE'/mcp-server/current"

# Start new MCP server
echo -e "'$YELLOW'▶️ Starting MCP server on port '$MCP_PORT'...'$NC'"
cd "'$DEPLOY_BASE'/mcp-server/current"
source venv/bin/activate
export PYTHONPATH="'$DEPLOY_BASE'/ai-ethical-dm:$PYTHONPATH"

# Start server with proper Python path
nohup python enhanced_ontology_server_with_guidelines.py > ../logs/mcp_'$TIMESTAMP'.log 2>&1 &
MCP_PID=$!

# Wait for startup
echo -e "'$YELLOW'⏳ Waiting for server startup...'$NC'"
sleep 10

# Check if process is still running
if ps -p $MCP_PID > /dev/null; then
    echo -e "'$GREEN'✅ MCP server process started (PID: $MCP_PID)'$NC'"
else
    echo -e "'$RED'❌ MCP server process failed to start'$NC'"
    echo "Last 20 lines of log:"
    tail -20 ../logs/mcp_'$TIMESTAMP'.log
    exit 1
fi

# Health check
echo -e "'$YELLOW'🏥 Performing health check...'$NC'"
MAX_RETRIES=6
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s -f http://localhost:'$MCP_PORT'/health 2>/dev/null; then
        echo -e "'$GREEN'✅ Health check passed!'$NC'"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            echo "Health check attempt $RETRY_COUNT/$MAX_RETRIES failed, retrying in 5s..."
            sleep 5
        else
            echo -e "'$RED'❌ Health check failed after $MAX_RETRIES attempts'$NC'"
            echo "Server log tail:"
            tail -20 ../logs/mcp_'$TIMESTAMP'.log
            exit 1
        fi
    fi
done

# Cleanup old releases (keep last 3)
echo -e "'$YELLOW'🧹 Cleaning up old releases...'$NC'"
cd "'$DEPLOY_BASE'/mcp-server/releases"
ls -1t | tail -n +4 | xargs rm -rf 2>/dev/null || true

echo -e "'$GREEN'🎉 MCP server deployment completed successfully!'$NC'"
echo -e "'$BLUE'📊 Server: http://localhost:'$MCP_PORT''$NC'"
echo -e "'$BLUE'📋 Logs: tail -f '$DEPLOY_BASE'/mcp-server/logs/mcp_'$TIMESTAMP'.log'$NC'"
echo -e "'$BLUE'🌿 Branch: '$BRANCH''$NC'"
echo -e "'$BLUE'💾 Commit: $(cd '$DEPLOY_BASE'/ai-ethical-dm && git rev-parse --short HEAD)'$NC'"
EOF

# Cleanup local files
rm -f "/tmp/mcp_deploy_$TIMESTAMP.tar.gz"
rm -rf "$TEMP_DIR"

echo
echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo
echo -e "${BLUE}📋 Summary:${NC}"
echo -e "${BLUE}  - Environment: $ENVIRONMENT${NC}"
echo -e "${BLUE}  - Branch: $BRANCH${NC}"
echo -e "${BLUE}  - Server: $SSH_HOST:$MCP_PORT${NC}"
echo -e "${BLUE}  - Location: $DEPLOY_BASE/mcp-server/current${NC}"
echo
echo -e "${YELLOW}📊 Next steps:${NC}"
echo "1. Check health: ./health-check.sh $ENVIRONMENT"
echo "2. View logs: ssh $SSH_USER@$SSH_HOST 'tail -f $DEPLOY_BASE/mcp-server/logs/mcp_*.log'"
echo "3. Test API: curl http://$SSH_HOST:$MCP_PORT/health"