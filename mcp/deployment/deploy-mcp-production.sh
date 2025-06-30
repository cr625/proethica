#!/bin/bash
# Production MCP Server Deployment Script
# Implements best practices for robust deployment

set -e  # Exit on error
set -u  # Exit on undefined variable
set -o pipefail  # Exit on pipe failure

# Configuration
DEPLOY_HOST="${DEPLOY_HOST:-digitalocean}"
DEPLOY_USER="${DEPLOY_USER:-chris}"
BRANCH="${1:-develop}"
REPO_URL="https://github.com/cr625/proethica.git"
MCP_PORT="5002"

# Paths
DEPLOY_BASE="/opt/proethica-mcp"
REPO_PATH="/home/chris/proethica-repo"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Pre-flight checks
log_info "🚀 ProEthica MCP Production Deployment"
log_info "Branch: $BRANCH"
log_info "Timestamp: $TIMESTAMP"
echo

# Check SSH connection
log_info "Testing SSH connection..."
if ! ssh -o ConnectTimeout=10 -o BatchMode=yes "$DEPLOY_USER@$DEPLOY_HOST" exit 2>/dev/null; then
    log_error "Cannot connect to $DEPLOY_HOST"
    exit 1
fi
log_success "SSH connection established"

# Check if infrastructure exists
log_info "Checking deployment infrastructure..."
ssh "$DEPLOY_USER@$DEPLOY_HOST" bash << 'EOF'
set -e

# Check if running as user deployment (temporary, will migrate later)
if [ ! -d "/home/chris/proethica-repo" ]; then
    echo "ERROR: Repository not found at /home/chris/proethica-repo"
    exit 1
fi

# Create deployment structure if it doesn't exist
if [ ! -d "/opt/proethica-mcp" ]; then
    echo "NOTICE: /opt/proethica-mcp doesn't exist. Using home directory deployment."
    
    # Create structure in home directory
    mkdir -p ~/proethica-deployment/{releases,shared/{logs,data},scripts,config}
    echo "Created deployment structure in ~/proethica-deployment"
fi
EOF

# Deployment
log_info "Starting deployment process..."

ssh "$DEPLOY_USER@$DEPLOY_HOST" bash << EOF
set -e

# Configuration
BRANCH="$BRANCH"
TIMESTAMP="$TIMESTAMP"
REPO_PATH="$REPO_PATH"
MCP_PORT="$MCP_PORT"

# Determine deployment base
if [ -d "/opt/proethica-mcp" ] && [ -w "/opt/proethica-mcp/releases" ]; then
    DEPLOY_BASE="/opt/proethica-mcp"
else
    DEPLOY_BASE="\$HOME/proethica-deployment"
    echo "Using home directory deployment: \$DEPLOY_BASE"
fi

RELEASE_DIR="\$DEPLOY_BASE/releases/\$TIMESTAMP"
CURRENT_LINK="\$DEPLOY_BASE/current"

# Update repository
echo -e "${YELLOW}Updating repository...${NC}"
cd "\$REPO_PATH"
git fetch origin
git checkout "\$BRANCH"
git pull origin "\$BRANCH"
COMMIT_HASH=\$(git rev-parse --short HEAD)
echo "Current commit: \$COMMIT_HASH"

# Create release directory
echo -e "${YELLOW}Creating release directory...${NC}"
mkdir -p "\$RELEASE_DIR"

# Copy MCP files
echo -e "${YELLOW}Copying MCP files...${NC}"
cp -r "\$REPO_PATH/mcp" "\$RELEASE_DIR/"
cp "\$REPO_PATH/requirements.txt" "\$RELEASE_DIR/" 2>/dev/null || true
cp "\$REPO_PATH/requirements-mcp.txt" "\$RELEASE_DIR/" 2>/dev/null || true

# Copy app directory for imports
cp -r "\$REPO_PATH/app" "\$RELEASE_DIR/"

# Create deployment info
cat > "\$RELEASE_DIR/deployment-info.json" << DEPLOY_INFO
{
    "timestamp": "\$TIMESTAMP",
    "branch": "\$BRANCH",
    "commit": "\$COMMIT_HASH",
    "deployed_by": "\$USER",
    "deployed_from": "\$(hostname)",
    "deployment_date": "\$(date -Iseconds)"
}
DEPLOY_INFO

# Setup Python environment
echo -e "${YELLOW}Setting up Python environment...${NC}"
cd "\$RELEASE_DIR"
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
pip install --upgrade pip setuptools wheel

# Install requirements
if [ -f "requirements-mcp.txt" ]; then
    echo "Installing from requirements-mcp.txt"
    pip install -r requirements-mcp.txt
elif [ -f "requirements.txt" ]; then
    echo "Installing from requirements.txt"
    pip install -r requirements.txt
else
    echo -e "${RED}No requirements file found!${NC}"
    exit 1
fi

# Setup shared resources
echo -e "${YELLOW}Setting up shared resources...${NC}"

# Create/update .env file
if [ -f "\$DEPLOY_BASE/shared/.env" ]; then
    ln -sf "\$DEPLOY_BASE/shared/.env" "\$RELEASE_DIR/.env"
else
    # Create template .env
    cat > "\$DEPLOY_BASE/shared/.env" << 'ENV_TEMPLATE'
# MCP Server Configuration
MCP_SERVER_PORT=$MCP_PORT
ENVIRONMENT=production
USE_MOCK_GUIDELINE_RESPONSES=false

# Database
DATABASE_URL=postgresql://postgres:PASS@localhost:5433/ai_ethical_dm

# Paths
ONTOLOGY_DIR=\$RELEASE_DIR/ontologies
PYTHONPATH=\$RELEASE_DIR:\$RELEASE_DIR/mcp

# API Keys (add your keys here)
# ANTHROPIC_API_KEY=
# MCP_AUTH_TOKEN=

# Logging
LOG_LEVEL=INFO
ENV_TEMPLATE
    
    ln -sf "\$DEPLOY_BASE/shared/.env" "\$RELEASE_DIR/.env"
    echo -e "${YELLOW}Created .env template - please add API keys${NC}"
fi

# Link logs directory
ln -sf "\$DEPLOY_BASE/shared/logs" "\$RELEASE_DIR/logs"

# Test MCP server import
echo -e "${YELLOW}Testing MCP server...${NC}"
cd "\$RELEASE_DIR"
source venv/bin/activate
export PYTHONPATH="\$RELEASE_DIR:\$RELEASE_DIR/mcp"

# Try to import the server
if python -c "import sys; sys.path.insert(0, '.'); sys.path.insert(0, 'mcp'); from http_ontology_mcp_server import OntologyMCPServer" 2>/dev/null; then
    echo -e "${GREEN}MCP server import test passed${NC}"
else
    echo -e "${RED}MCP server import test failed${NC}"
    echo "Trying with enhanced server..."
    
    if python -c "import sys; sys.path.insert(0, '.'); from mcp.enhanced_ontology_server_with_guidelines import EnhancedOntologyMCPServer" 2>/dev/null; then
        echo -e "${GREEN}Enhanced MCP server import test passed${NC}"
    else
        echo -e "${RED}All import tests failed${NC}"
        exit 1
    fi
fi

# Stop current MCP server
echo -e "${YELLOW}Stopping current MCP server...${NC}"
if [ -f "\$CURRENT_LINK/mcp-server.pid" ]; then
    OLD_PID=\$(cat "\$CURRENT_LINK/mcp-server.pid" 2>/dev/null || echo "")
    if [ -n "\$OLD_PID" ] && kill -0 "\$OLD_PID" 2>/dev/null; then
        kill "\$OLD_PID"
        sleep 3
    fi
fi

# Also kill any orphaned processes
pkill -f "http_ontology_mcp_server.py" || true
pkill -f "enhanced_ontology_server" || true
sleep 2

# Update current symlink
echo -e "${YELLOW}Updating current symlink...${NC}"
ln -sfn "\$RELEASE_DIR" "\$CURRENT_LINK"

# Start new MCP server
echo -e "${YELLOW}Starting MCP server...${NC}"
cd "\$CURRENT_LINK"
source venv/bin/activate
export PYTHONPATH="\$CURRENT_LINK:\$CURRENT_LINK/mcp"
source .env

# Determine which server to start
if [ -f "mcp/http_ontology_mcp_server.py" ]; then
    SERVER_SCRIPT="mcp/http_ontology_mcp_server.py"
elif [ -f "mcp/enhanced_ontology_server_with_guidelines.py" ]; then
    SERVER_SCRIPT="mcp/enhanced_ontology_server_with_guidelines.py"
else
    echo -e "${RED}No MCP server script found!${NC}"
    exit 1
fi

# Start server
nohup python "\$SERVER_SCRIPT" > "\$DEPLOY_BASE/shared/logs/mcp_\$TIMESTAMP.log" 2>&1 &
MCP_PID=\$!
echo \$MCP_PID > mcp-server.pid

# Wait for startup
echo -e "${YELLOW}Waiting for server startup...${NC}"
sleep 10

# Check if process is running
if kill -0 \$MCP_PID 2>/dev/null; then
    echo -e "${GREEN}MCP server started (PID: \$MCP_PID)${NC}"
else
    echo -e "${RED}MCP server failed to start${NC}"
    echo "Last 50 lines of log:"
    tail -50 "\$DEPLOY_BASE/shared/logs/mcp_\$TIMESTAMP.log"
    exit 1
fi

# Health check
echo -e "${YELLOW}Performing health check...${NC}"
MAX_RETRIES=12
RETRY_COUNT=0
HEALTH_CHECK_PASSED=false

while [ \$RETRY_COUNT -lt \$MAX_RETRIES ]; do
    if curl -sf http://localhost:\$MCP_PORT/health >/dev/null 2>&1; then
        echo -e "${GREEN}Health check passed!${NC}"
        HEALTH_CHECK_PASSED=true
        break
    else
        RETRY_COUNT=\$((RETRY_COUNT + 1))
        if [ \$RETRY_COUNT -lt \$MAX_RETRIES ]; then
            echo "Health check attempt \$RETRY_COUNT/\$MAX_RETRIES failed, retrying in 5s..."
            sleep 5
        fi
    fi
done

if [ "\$HEALTH_CHECK_PASSED" = false ]; then
    echo -e "${RED}Health check failed after \$MAX_RETRIES attempts${NC}"
    echo "Server log tail:"
    tail -50 "\$DEPLOY_BASE/shared/logs/mcp_\$TIMESTAMP.log"
    exit 1
fi

# Cleanup old releases (keep last 5)
echo -e "${YELLOW}Cleaning up old releases...${NC}"
cd "\$DEPLOY_BASE/releases"
ls -1t | tail -n +6 | xargs rm -rf 2>/dev/null || true

# Success summary
echo
echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}Branch:${NC} \$BRANCH"
echo -e "${BLUE}Commit:${NC} \$COMMIT_HASH"
echo -e "${BLUE}Release:${NC} \$RELEASE_DIR"
echo -e "${BLUE}Port:${NC} \$MCP_PORT"
echo -e "${BLUE}PID:${NC} \$MCP_PID"
echo -e "${BLUE}Logs:${NC} tail -f \$DEPLOY_BASE/shared/logs/mcp_\$TIMESTAMP.log"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
EOF

# Final status
echo
log_success "Deployment completed!"
echo
echo "Next steps:"
echo "1. Verify: curl http://$DEPLOY_HOST:$MCP_PORT/health"
echo "2. Configure nginx: sudo ln -s /etc/nginx/sites-available/mcp.proethica.org /etc/nginx/sites-enabled/"
echo "3. SSL certificate: sudo certbot --nginx -d mcp.proethica.org"
echo "4. Monitor logs: ssh $DEPLOY_USER@$DEPLOY_HOST 'tail -f ~/proethica-deployment/shared/logs/mcp_*.log'"