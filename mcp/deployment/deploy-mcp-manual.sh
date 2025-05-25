#!/bin/bash
# Manual MCP Server Deployment Script
# Usage: ./deploy-mcp-manual.sh [production|staging]

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT=${1:-production}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

echo -e "${BLUE}🚀 ProEthica MCP Server Manual Deployment${NC}"
echo -e "${BLUE}===========================================${NC}"
echo -e "${YELLOW}Environment: $ENVIRONMENT${NC}"
echo

# Load environment-specific configuration
case $ENVIRONMENT in
    production)
        SSH_HOST="proethica.org"
        SSH_USER="chris"
        MCP_PORT="5002"
        ;;
    staging)
        SSH_HOST="staging.proethica.org"
        SSH_USER="chris"
        MCP_PORT="5003"
        ;;
    *)
        echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
        echo "Usage: $0 [production|staging]"
        exit 1
        ;;
esac

# Check if we can connect to the server
echo -e "${YELLOW}🔗 Testing SSH connection to $SSH_HOST...${NC}"
if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "$SSH_USER@$SSH_HOST" exit 2>/dev/null; then
    echo -e "${RED}❌ Cannot connect to $SSH_HOST${NC}"
    echo "Please check your SSH configuration and server availability."
    exit 1
fi
echo -e "${GREEN}✅ SSH connection successful${NC}"

# Validate local MCP server files
echo -e "${YELLOW}🔍 Validating local MCP server files...${NC}"
cd "$PROJECT_ROOT"

if [[ ! -f "mcp/enhanced_ontology_server_with_guidelines.py" ]]; then
    echo -e "${RED}❌ MCP server file not found${NC}"
    exit 1
fi

if [[ ! -f "requirements-mcp.txt" ]]; then
    echo -e "${RED}❌ MCP requirements file not found${NC}"
    exit 1
fi

# Syntax check
python3 -m py_compile mcp/enhanced_ontology_server_with_guidelines.py
echo -e "${GREEN}✅ MCP server syntax validation passed${NC}"

# Create deployment package
echo -e "${YELLOW}📦 Creating deployment package...${NC}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TEMP_DIR="/tmp/mcp_deploy_$TIMESTAMP"
mkdir -p "$TEMP_DIR"

# Copy MCP files
cp -r mcp/* "$TEMP_DIR/"
cp requirements-mcp.txt "$TEMP_DIR/"

# Create deployment archive
cd /tmp
tar -czf "mcp_deploy_$TIMESTAMP.tar.gz" "mcp_deploy_$TIMESTAMP"
echo -e "${GREEN}✅ Deployment package created: mcp_deploy_$TIMESTAMP.tar.gz${NC}"

# Upload and deploy
echo -e "${YELLOW}📤 Uploading and deploying to $SSH_HOST...${NC}"

ssh "$SSH_USER@$SSH_HOST" << EOF
set -e

echo -e "${YELLOW}🏗️ Setting up deployment environment...${NC}"

# Configuration
DEPLOY_DIR="/home/chris/proethica"
MCP_DIR="\$DEPLOY_DIR/mcp-server"
RELEASE_DIR="\$MCP_DIR/releases/$TIMESTAMP"

# Create directory structure
mkdir -p "\$MCP_DIR"/{current,releases,shared,logs}
mkdir -p "\$RELEASE_DIR"

echo -e "${YELLOW}📁 Created release directory: \$RELEASE_DIR${NC}"
EOF

# Transfer deployment package
echo -e "${YELLOW}📤 Transferring files...${NC}"
scp "/tmp/mcp_deploy_$TIMESTAMP.tar.gz" "$SSH_USER@$SSH_HOST:/tmp/"

# Continue deployment on remote server
ssh "$SSH_USER@$SSH_HOST" << EOF
set -e

cd /tmp
tar -xzf "mcp_deploy_$TIMESTAMP.tar.gz"
mv "mcp_deploy_$TIMESTAMP"/* "$RELEASE_DIR/"
rm -f "mcp_deploy_$TIMESTAMP.tar.gz"
rm -rf "mcp_deploy_$TIMESTAMP"

# Set up Python environment
cd "\$RELEASE_DIR"
echo -e "${YELLOW}🐍 Setting up Python environment...${NC}"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements-mcp.txt

# Create environment file
echo -e "${YELLOW}⚙️ Creating environment configuration...${NC}"
cat > .env << 'ENVEOF'
MCP_SERVER_PORT=$MCP_PORT
USE_MOCK_GUIDELINE_RESPONSES=false
DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm
ENVIRONMENT=$ENVIRONMENT
ENVEOF

# Note: In production, you should set these via secure methods
echo "# Add your API keys to this file:" >> .env
echo "# ANTHROPIC_API_KEY=your-key-here" >> .env
echo "# MCP_AUTH_TOKEN=your-token-here" >> .env

# Test server startup
echo -e "${YELLOW}🧪 Testing MCP server startup...${NC}"
source venv/bin/activate
if timeout 30s python enhanced_ontology_server_with_guidelines.py --test-mode; then
    echo -e "${GREEN}✅ MCP server startup test passed${NC}"
else
    echo -e "${RED}❌ MCP server startup test failed${NC}"
    exit 1
fi

# Stop existing MCP server
echo -e "${YELLOW}⏹️ Stopping existing MCP server...${NC}"
pkill -f "enhanced_ontology_server_with_guidelines.py" || echo "No existing server found"
sleep 2

# Update current symlink
ln -sfn "\$RELEASE_DIR" "\$MCP_DIR/current"

# Start new MCP server
echo -e "${YELLOW}▶️ Starting new MCP server on port $MCP_PORT...${NC}"
cd "\$MCP_DIR/current"
source venv/bin/activate
nohup python enhanced_ontology_server_with_guidelines.py > ../logs/mcp_$TIMESTAMP.log 2>&1 &

# Wait for startup
sleep 5

# Health check
echo -e "${YELLOW}🏥 Performing health check...${NC}"
if curl -f http://localhost:$MCP_PORT/health 2>/dev/null; then
    echo -e "${GREEN}✅ MCP server health check passed${NC}"
else
    echo -e "${RED}❌ MCP server health check failed${NC}"
    echo "Check logs: tail -f \$MCP_DIR/logs/mcp_$TIMESTAMP.log"
    exit 1
fi

# Cleanup old releases (keep last 3)
echo -e "${YELLOW}🧹 Cleaning up old releases...${NC}"
cd "\$MCP_DIR/releases"
ls -1t | tail -n +4 | xargs rm -rf || true

echo -e "${GREEN}🎉 MCP server deployment completed successfully!${NC}"
echo -e "${BLUE}📊 Server status: http://localhost:$MCP_PORT/health${NC}"
echo -e "${BLUE}📋 View logs: tail -f \$MCP_DIR/logs/mcp_$TIMESTAMP.log${NC}"
EOF

# Cleanup local temp files
rm -f "/tmp/mcp_deploy_$TIMESTAMP.tar.gz"
rm -rf "$TEMP_DIR"

echo
echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo -e "${BLUE}🌐 MCP Server: http://$SSH_HOST:$MCP_PORT${NC}"
echo -e "${BLUE}📊 Health Check: http://$SSH_HOST:$MCP_PORT/health${NC}"
echo -e "${BLUE}📋 View logs: ssh $SSH_USER@$SSH_HOST 'tail -f /home/chris/proethica/mcp-server/logs/mcp_*.log'${NC}"