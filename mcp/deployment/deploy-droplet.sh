#!/bin/bash
# Deployment script for Digital Ocean Droplet

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}ProEthica MCP Server Deployment Script${NC}"
echo "======================================="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root${NC}"
   exit 1
fi

# Update system
echo -e "${YELLOW}Updating system packages...${NC}"
apt update && apt upgrade -y

# Install dependencies
echo -e "${YELLOW}Installing system dependencies...${NC}"
apt install -y python3 python3-pip python3-venv nginx certbot python3-certbot-nginx postgresql postgresql-contrib

# Create application user
echo -e "${YELLOW}Creating application user...${NC}"
useradd -m -s /bin/bash proethica || echo "User already exists"

# Create application directory
echo -e "${YELLOW}Setting up application directory...${NC}"
mkdir -p /opt/proethica-mcp
chown proethica:proethica /opt/proethica-mcp

# Clone or update repository
echo -e "${YELLOW}Cloning/updating repository...${NC}"
if [ -d "/opt/proethica-mcp/ai-ethical-dm" ]; then
    cd /opt/proethica-mcp/ai-ethical-dm
    sudo -u proethica git pull
else
    cd /opt/proethica-mcp
    sudo -u proethica git clone https://github.com/your-username/ai-ethical-dm.git
fi

# Create Python virtual environment
echo -e "${YELLOW}Setting up Python environment...${NC}"
cd /opt/proethica-mcp/ai-ethical-dm
sudo -u proethica python3 -m venv venv
sudo -u proethica ./venv/bin/pip install --upgrade pip
sudo -u proethica ./venv/bin/pip install -r requirements-mcp.txt

# Create systemd service
echo -e "${YELLOW}Creating systemd service...${NC}"
cat > /etc/systemd/system/proethica-mcp.service << 'EOF'
[Unit]
Description=ProEthica MCP Server
After=network.target postgresql.service

[Service]
Type=simple
User=proethica
Group=proethica
WorkingDirectory=/opt/proethica-mcp/ai-ethical-dm
Environment="PATH=/opt/proethica-mcp/ai-ethical-dm/venv/bin"
EnvironmentFile=/opt/proethica-mcp/.env
ExecStart=/opt/proethica-mcp/ai-ethical-dm/venv/bin/python mcp/run_enhanced_mcp_server_with_guidelines.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create environment file template
echo -e "${YELLOW}Creating environment file template...${NC}"
cat > /opt/proethica-mcp/.env.template << 'EOF'
# MCP Server Configuration
MCP_SERVER_PORT=5001
USE_MOCK_GUIDELINE_RESPONSES=false

# Database Configuration
DATABASE_URL=postgresql://proethica:password@localhost:5432/proethica_db

# API Keys (Required)
ANTHROPIC_API_KEY=your-anthropic-api-key
OPENAI_API_KEY=your-openai-api-key  # Optional

# Authentication Token for MCP Access
MCP_AUTH_TOKEN=generate-a-secure-token-here
EOF

# Set up nginx
echo -e "${YELLOW}Setting up nginx...${NC}"
cp /opt/proethica-mcp/ai-ethical-dm/mcp/deployment/nginx-mcp.conf /etc/nginx/sites-available/mcp.proethica.org
ln -sf /etc/nginx/sites-available/mcp.proethica.org /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# Set up SSL with Let's Encrypt
echo -e "${YELLOW}Setting up SSL certificate...${NC}"
echo -e "${GREEN}Run this command to set up SSL:${NC}"
echo "certbot --nginx -d mcp.proethica.org"

# Create database
echo -e "${YELLOW}Setting up PostgreSQL database...${NC}"
sudo -u postgres psql << EOF
CREATE USER proethica WITH PASSWORD 'change-this-password';
CREATE DATABASE proethica_db OWNER proethica;
GRANT ALL PRIVILEGES ON DATABASE proethica_db TO proethica;
EOF

# Final instructions
echo -e "${GREEN}Deployment almost complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Copy /opt/proethica-mcp/.env.template to /opt/proethica-mcp/.env"
echo "2. Edit /opt/proethica-mcp/.env with your actual API keys and database password"
echo "3. Run: systemctl daemon-reload"
echo "4. Run: systemctl enable proethica-mcp"
echo "5. Run: systemctl start proethica-mcp"
echo "6. Run: certbot --nginx -d mcp.proethica.org"
echo ""
echo "Check status with: systemctl status proethica-mcp"
echo "View logs with: journalctl -u proethica-mcp -f"