#!/bin/bash
# Setup script for adding MCP server to existing ProEthica droplet

set -e  # Exit on error

echo "ProEthica MCP Server Setup"
echo "=========================="

# Variables - update these for your setup
REPO_PATH="/var/www/proethica"
VENV_PATH="/var/www/proethica/venv"
NGINX_CONF="/etc/nginx/sites-available/proethica.org"  # Update if different

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}Step 1: Creating directories...${NC}"
sudo mkdir -p /etc/proethica
sudo mkdir -p /var/log/proethica
sudo chown www-data:www-data /var/log/proethica

echo -e "${YELLOW}Step 2: Installing Python dependencies...${NC}"
cd $REPO_PATH
# Use the virtual environment's pip directly
$VENV_PATH/bin/pip install -r requirements-mcp.txt

echo -e "${YELLOW}Step 3: Setting up environment file...${NC}"
if [ ! -f /etc/proethica/mcp.env ]; then
    sudo cp mcp/deployment/mcp.env.example /etc/proethica/mcp.env
    sudo chmod 600 /etc/proethica/mcp.env
    echo -e "${RED}IMPORTANT: Edit /etc/proethica/mcp.env with your API keys and settings${NC}"
fi

echo -e "${YELLOW}Step 4: Installing systemd service...${NC}"
# Update paths in service file
sed -e "s|/path/to/your/ai-ethical-dm|$REPO_PATH|g" \
    -e "s|/path/to/your/venv|$VENV_PATH|g" \
    mcp/deployment/proethica-mcp.service > /tmp/proethica-mcp.service

sudo cp /tmp/proethica-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload

echo -e "${YELLOW}Step 5: Generate secure auth token...${NC}"
AUTH_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")
echo -e "${GREEN}Generated auth token: ${AUTH_TOKEN}${NC}"
echo "Add this to /etc/proethica/mcp.env as MCP_AUTH_TOKEN"

echo -e "${YELLOW}Step 6: Nginx configuration...${NC}"
echo -e "${RED}MANUAL STEP REQUIRED:${NC}"
echo "Add the location blocks from nginx-mcp-location.conf to your nginx config"
echo "File: $NGINX_CONF"
echo ""
echo "After adding, test with: sudo nginx -t"
echo "Then reload: sudo systemctl reload nginx"

echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Edit /etc/proethica/mcp.env with your settings"
echo "2. Add MCP_AUTH_TOKEN=$AUTH_TOKEN to the env file"
echo "3. Add nginx location blocks to your config"
echo "4. Start the service:"
echo "   sudo systemctl enable proethica-mcp"
echo "   sudo systemctl start proethica-mcp"
echo ""
echo "Check status: sudo systemctl status proethica-mcp"
echo "View logs: sudo journalctl -u proethica-mcp -f"