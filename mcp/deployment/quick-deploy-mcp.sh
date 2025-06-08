#!/bin/bash
# Quick MCP Deployment Script
# Gets MCP server running immediately while planning migration to best practices

set -e

# Configuration
DEPLOY_HOST="${1:-digitalocean}"
BRANCH="${2:-develop}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}🚀 Quick MCP Deployment${NC}"
echo -e "${BLUE}Host: $DEPLOY_HOST${NC}"
echo -e "${BLUE}Branch: $BRANCH${NC}"
echo

# Deploy
ssh "$DEPLOY_HOST" bash -s << EOF
set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
REPO_DIR="\$HOME/proethica-repo"
MCP_DIR="\$HOME/proethica-mcp"
BRANCH="$BRANCH"

# Update repository
echo -e "\${YELLOW}Updating repository...\${NC}"
cd "\$REPO_DIR"
git fetch origin
git checkout "\$BRANCH"
git pull origin "\$BRANCH"
COMMIT=\$(git rev-parse --short HEAD)
echo -e "\${GREEN}Updated to commit: \$COMMIT\${NC}"

# Sync MCP files
echo -e "\${YELLOW}Syncing MCP files...\${NC}"
rsync -av --delete \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    --exclude='.git' \
    "\$REPO_DIR/mcp/" "\$MCP_DIR/mcp/"

# Copy requirements
cp "\$REPO_DIR/requirements-mcp.txt" "\$MCP_DIR/" 2>/dev/null || \
cp "\$REPO_DIR/requirements.txt" "\$MCP_DIR/requirements-mcp.txt"

# Update virtual environment
echo -e "\${YELLOW}Updating Python dependencies...\${NC}"
cd "\$MCP_DIR"
if [ ! -d "mcp-venv" ]; then
    echo -e "\${YELLOW}Creating virtual environment...\${NC}"
    python3 -m venv mcp-venv
fi
source mcp-venv/bin/activate
pip install --upgrade pip
pip install -r requirements-mcp.txt

# Setup environment
if [ ! -f "\$MCP_DIR/mcp.env" ]; then
    cat > "\$MCP_DIR/mcp.env" << 'ENV'
# MCP Server Configuration
export PYTHONPATH=/home/chris/proethica-mcp:/home/chris/proethica-repo
export ONTOLOGY_DIR=/home/chris/proethica-repo/ontologies
export DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm
export MCP_SERVER_PORT=5002
export USE_MOCK_GUIDELINE_RESPONSES=false
ENV
    echo -e "\${YELLOW}Created mcp.env - add API keys if needed\${NC}"
fi

# Source environment
source mcp.env

# Stop existing server
echo -e "\${YELLOW}Stopping existing MCP server...\${NC}"
pkill -f "ontology_mcp_server" || true
sleep 3

# Create logs directory if needed
mkdir -p logs

# Start new server
echo -e "\${YELLOW}Starting MCP server...\${NC}"
cd "\$MCP_DIR"
source mcp-venv/bin/activate
source mcp.env

# Determine which server to use
if [ -f "mcp/http_ontology_mcp_server.py" ]; then
    SERVER="mcp/http_ontology_mcp_server.py"
elif [ -f "mcp/enhanced_ontology_server_with_guidelines.py" ]; then
    SERVER="mcp/enhanced_ontology_server_with_guidelines.py"
else
    echo -e "\${RED}No MCP server found!\${NC}"
    exit 1
fi

# Start server
nohup python "\$SERVER" > logs/mcp-\$(date +%Y%m%d-%H%M%S).log 2>&1 &
PID=\$!
echo \$PID > mcp-server.pid

# Wait and check
sleep 10
if kill -0 \$PID 2>/dev/null; then
    echo -e "\${GREEN}✓ MCP server started (PID: \$PID)\${NC}"
else
    echo -e "\${RED}✗ MCP server failed to start\${NC}"
    tail -20 logs/mcp-*.log
    exit 1
fi

# Health check
echo -e "\${YELLOW}Testing health endpoint...\${NC}"
for i in {1..6}; do
    if curl -sf http://localhost:5002/health >/dev/null 2>&1; then
        echo -e "\${GREEN}✓ Health check passed!\${NC}"
        break
    else
        echo "Attempt \$i/6 failed, retrying..."
        sleep 5
    fi
done

echo
echo -e "\${GREEN}🎉 Quick deployment complete!\${NC}"
echo -e "\${BLUE}Server: http://localhost:5002\${NC}"
echo -e "\${BLUE}Logs: tail -f \$MCP_DIR/logs/mcp-*.log\${NC}"
EOF

echo
echo -e "${GREEN}Deployment finished!${NC}"
echo
echo "Next steps:"
echo "1. Test locally: curl http://$DEPLOY_HOST:5002/health"
echo "2. Configure nginx: See nginx-mcp-ssl.conf"
echo "3. Enable SSL: sudo certbot --nginx -d mcp.proethica.org"
echo "4. Monitor: ./check-mcp-health.sh $DEPLOY_HOST"