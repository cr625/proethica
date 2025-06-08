#!/bin/bash
# MCP Server Health Check Script
# Can be run locally or remotely

set -e

# Configuration
HOST="${1:-localhost}"
PORT="${2:-5002}"
DEPLOY_HOST="${DEPLOY_HOST:-digitalocean}"
DEPLOY_USER="${DEPLOY_USER:-chris}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Functions
check_local() {
    echo -e "${BLUE}Checking MCP server locally...${NC}"
    
    # Check if process is running
    if pgrep -f "ontology_mcp_server" > /dev/null; then
        echo -e "${GREEN}✓${NC} MCP process is running"
        
        # Get PID and details
        PID=$(pgrep -f "ontology_mcp_server" | head -1)
        echo -e "  PID: $PID"
        echo -e "  Memory: $(ps -o rss= -p $PID | awk '{print int($1/1024) "MB"}')"
    else
        echo -e "${RED}✗${NC} MCP process not found"
    fi
    
    # Check health endpoint
    echo -e "\n${BLUE}Testing health endpoint...${NC}"
    if curl -sf "http://$HOST:$PORT/health" > /dev/null; then
        echo -e "${GREEN}✓${NC} Health endpoint responding"
        
        # Get detailed health info if available
        HEALTH_RESPONSE=$(curl -s "http://$HOST:$PORT/health")
        echo -e "  Response: $HEALTH_RESPONSE"
    else
        echo -e "${RED}✗${NC} Health endpoint not responding"
        return 1
    fi
    
    # Check other endpoints
    echo -e "\n${BLUE}Testing API endpoints...${NC}"
    
    # Test root endpoint
    if curl -sf "http://$HOST:$PORT/" > /dev/null; then
        echo -e "${GREEN}✓${NC} Root endpoint responding"
    else
        echo -e "${YELLOW}⚠${NC} Root endpoint not responding (may be normal)"
    fi
    
    # Test RPC endpoint
    RPC_TEST=$(curl -s -X POST "http://$HOST:$PORT/" \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","method":"health","params":{},"id":1}' 2>/dev/null || echo "")
    
    if [[ "$RPC_TEST" == *"result"* ]]; then
        echo -e "${GREEN}✓${NC} JSON-RPC endpoint responding"
    else
        echo -e "${YELLOW}⚠${NC} JSON-RPC endpoint not responding"
    fi
}

check_remote() {
    echo -e "${BLUE}Checking MCP server on $DEPLOY_HOST...${NC}"
    
    # Check SSH connection
    if ! ssh -o ConnectTimeout=5 -o BatchMode=yes "$DEPLOY_USER@$DEPLOY_HOST" exit 2>/dev/null; then
        echo -e "${RED}✗${NC} Cannot connect to $DEPLOY_HOST"
        return 1
    fi
    
    # Run checks on remote host
    ssh "$DEPLOY_USER@$DEPLOY_HOST" bash << 'EOF'
    # Check process
    echo -e "\033[0;34mProcess Status:\033[0m"
    if pgrep -f "ontology_mcp_server" > /dev/null; then
        PID=$(pgrep -f "ontology_mcp_server" | head -1)
        echo -e "\033[0;32m✓\033[0m MCP process running (PID: $PID)"
        ps -p $PID -o pid,user,%cpu,%mem,etime,cmd --no-headers
    else
        echo -e "\033[0;31m✗\033[0m MCP process not found"
    fi
    
    # Check ports
    echo -e "\n\033[0;34mPort Status:\033[0m"
    if netstat -tlnp 2>/dev/null | grep -q ":5002"; then
        echo -e "\033[0;32m✓\033[0m Port 5002 is listening"
    else
        echo -e "\033[0;31m✗\033[0m Port 5002 is not listening"
    fi
    
    # Check logs
    echo -e "\n\033[0;34mRecent Logs:\033[0m"
    LOG_DIR="$HOME/proethica-deployment/shared/logs"
    if [ -d "$LOG_DIR" ]; then
        LATEST_LOG=$(ls -t "$LOG_DIR"/mcp_*.log 2>/dev/null | head -1)
        if [ -n "$LATEST_LOG" ]; then
            echo "Latest log: $LATEST_LOG"
            echo "Last 10 lines:"
            tail -10 "$LATEST_LOG" | sed 's/^/  /'
        fi
    fi
EOF
    
    # Test health endpoint from local
    echo -e "\n${BLUE}Testing remote health endpoint...${NC}"
    if curl -sf "http://$DEPLOY_HOST:$PORT/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Remote health endpoint responding"
    else
        echo -e "${RED}✗${NC} Remote health endpoint not responding"
        echo -e "${YELLOW}Note: This might be due to firewall rules${NC}"
    fi
}

# Main
echo -e "${GREEN}ProEthica MCP Health Check${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ "$HOST" == "localhost" ] || [ "$HOST" == "127.0.0.1" ]; then
    check_local
else
    check_remote
fi

echo -e "\n${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}Health check complete${NC}"