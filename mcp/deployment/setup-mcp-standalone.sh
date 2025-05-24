#!/bin/bash
# Setup script for MCP server in home directory

set -e  # Exit on error

echo "ProEthica MCP Server Setup (Standalone)"
echo "======================================="

# Variables
MCP_HOME="$HOME/proethica-mcp"
REPO_URL="https://github.com/your-username/ai-ethical-dm.git"  # Update this!

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}Step 1: Creating MCP home directory...${NC}"
mkdir -p $MCP_HOME
cd $MCP_HOME

echo -e "${YELLOW}Step 2: Cloning repository (or using existing)...${NC}"
if [ ! -d "ai-ethical-dm" ]; then
    git clone $REPO_URL
    cd ai-ethical-dm
else
    cd ai-ethical-dm
    git pull
fi

echo -e "${YELLOW}Step 3: Creating virtual environment...${NC}"
python3 -m venv mcp-venv
source mcp-venv/bin/activate

echo -e "${YELLOW}Step 4: Installing dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements-mcp.txt

echo -e "${YELLOW}Step 5: Creating config directories...${NC}"
mkdir -p $MCP_HOME/config
mkdir -p $MCP_HOME/logs

echo -e "${YELLOW}Step 6: Creating environment file...${NC}"
cat > $MCP_HOME/config/mcp.env << 'EOF'
# MCP Server Environment Variables
# Edit these values!

# API Keys
ANTHROPIC_API_KEY=your-anthropic-api-key
OPENAI_API_KEY=your-openai-api-key  # Optional

# Database (same as your main app)
DATABASE_URL=postgresql://user:password@localhost:5432/ai_ethical_dm

# Authentication
MCP_AUTH_TOKEN=generate-secure-token-here

# Server Configuration
MCP_SERVER_PORT=5001
USE_MOCK_GUIDELINE_RESPONSES=false

# Paths
PYTHONPATH=/home/$USER/proethica-mcp/ai-ethical-dm
EOF

echo -e "${YELLOW}Step 7: Generating auth token...${NC}"
AUTH_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo -e "${GREEN}Generated auth token: ${AUTH_TOKEN}${NC}"
echo "Update MCP_AUTH_TOKEN in $MCP_HOME/config/mcp.env"

echo -e "${YELLOW}Step 8: Creating systemd service...${NC}"
sudo tee /etc/systemd/system/proethica-mcp.service << EOF
[Unit]
Description=ProEthica MCP Server (Standalone)
After=network.target postgresql.service

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=$MCP_HOME/ai-ethical-dm
Environment="PATH=$MCP_HOME/ai-ethical-dm/mcp-venv/bin"
EnvironmentFile=$MCP_HOME/config/mcp.env
ExecStart=$MCP_HOME/ai-ethical-dm/mcp-venv/bin/python mcp/run_enhanced_mcp_server_with_guidelines.py
Restart=always
RestartSec=10
StandardOutput=append:$MCP_HOME/logs/mcp-server.log
StandardError=append:$MCP_HOME/logs/mcp-server-error.log

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload

echo -e "${YELLOW}Step 9: Creating run script...${NC}"
cat > $MCP_HOME/run-mcp.sh << 'EOF'
#!/bin/bash
# Quick run script for MCP server

cd $(dirname $0)/ai-ethical-dm
source mcp-venv/bin/activate
export $(cat ../config/mcp.env | grep -v '^#' | xargs)
python mcp/run_enhanced_mcp_server_with_guidelines.py
EOF
chmod +x $MCP_HOME/run-mcp.sh

echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "MCP Server installed in: $MCP_HOME"
echo ""
echo "Next steps:"
echo "1. Edit environment file: nano $MCP_HOME/config/mcp.env"
echo "2. Add your API keys and database connection"
echo "3. Update MCP_AUTH_TOKEN with: $AUTH_TOKEN"
echo "4. Add nginx proxy configuration (see nginx-mcp-location.conf)"
echo "5. Start the service:"
echo "   sudo systemctl enable proethica-mcp"
echo "   sudo systemctl start proethica-mcp"
echo ""
echo "Or run manually for testing:"
echo "   $MCP_HOME/run-mcp.sh"
echo ""
echo "Check logs at: $MCP_HOME/logs/"