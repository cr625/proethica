#!/bin/bash
# Script to update and install the Proethica service with the fixed configuration

# ANSI color codes for better readability
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=== Proethica Service Update Tool ===${NC}"

# Check if running as root/sudo
if [[ $EUID -ne 0 ]]; then
   echo -e "${YELLOW}This script needs to be run as root (sudo).${NC}"
   echo -e "Please run: sudo $0"
   exit 1
fi

# Copy the updated service file to systemd directory
echo -e "${BLUE}Copying updated service file...${NC}"
cp server_config/proethica.service.updated /etc/systemd/system/proethica.service

# Ensure the execution script is executable
echo -e "${BLUE}Ensuring scripts are executable...${NC}"
chmod +x /home/chris/proethica/run_proethica_with_agents.sh
chmod +x /home/chris/proethica/scripts/restart_mcp_server_gunicorn.fixed.sh

# Reload systemd to recognize the new service
echo -e "${BLUE}Reloading systemd...${NC}"
systemctl daemon-reload

# Check if the service is already enabled
if systemctl is-enabled proethica.service &>/dev/null; then
    echo -e "${BLUE}Service is already enabled. Restarting...${NC}"
    systemctl restart proethica.service
    
    # Check if restart was successful
    if systemctl is-active proethica.service &>/dev/null; then
        echo -e "${GREEN}Service successfully restarted!${NC}"
    else
        echo -e "${RED}Failed to restart service. Check status with: systemctl status proethica.service${NC}"
    fi
else
    echo -e "${YELLOW}Service is not yet enabled. To enable and start it, run:${NC}"
    echo -e "sudo systemctl enable proethica.service"
    echo -e "sudo systemctl start proethica.service"
fi

echo -e "${GREEN}Service update complete!${NC}"
echo -e "You can now manage the service with:"
echo -e "  sudo systemctl start proethica.service   - Start the service"
echo -e "  sudo systemctl stop proethica.service    - Stop the service"
echo -e "  sudo systemctl restart proethica.service - Restart the service"
echo -e "  sudo systemctl status proethica.service  - Check service status"
