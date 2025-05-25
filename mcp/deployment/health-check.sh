#!/bin/bash
# MCP Server Health Check Script
# Usage: ./health-check.sh [production|staging|local]

set -e

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ENVIRONMENT=${1:-production}

echo -e "${BLUE}🏥 ProEthica MCP Server Health Check${NC}"
echo -e "${BLUE}====================================${NC}"
echo -e "${YELLOW}Environment: $ENVIRONMENT${NC}"
echo

# Set configuration based on environment
case $ENVIRONMENT in
    production)
        MCP_URL="http://proethica.org:5002"
        SSH_HOST="proethica.org"
        SSH_USER="chris"
        ;;
    staging)
        MCP_URL="http://staging.proethica.org:5003"
        SSH_HOST="staging.proethica.org"
        SSH_USER="chris"
        ;;
    local)
        MCP_URL="http://localhost:5002"
        SSH_HOST=""
        SSH_USER=""
        ;;
    *)
        echo -e "${RED}❌ Invalid environment: $ENVIRONMENT${NC}"
        echo "Usage: $0 [production|staging|local]"
        exit 1
        ;;
esac

echo -e "${YELLOW}🔍 Checking MCP server at: $MCP_URL${NC}"

# Function to perform HTTP check
http_check() {
    local endpoint=$1
    local description=$2
    echo -n "  $description... "
    
    if curl -s -f --connect-timeout 10 "$MCP_URL$endpoint" > /dev/null; then
        echo -e "${GREEN}✅ OK${NC}"
        return 0
    else
        echo -e "${RED}❌ FAILED${NC}"
        return 1
    fi
}

# Function to check JSON response
json_check() {
    local endpoint=$1
    local description=$2
    echo -n "  $description... "
    
    local response=$(curl -s --connect-timeout 10 "$MCP_URL$endpoint")
    if echo "$response" | jq . > /dev/null 2>&1; then
        echo -e "${GREEN}✅ OK${NC}"
        return 0
    else
        echo -e "${RED}❌ FAILED${NC}"
        echo "    Response: $response"
        return 1
    fi
}

# Basic connectivity
echo -e "${YELLOW}🌐 Basic Connectivity${NC}"
HEALTH_FAILED=0

http_check "/health" "Health endpoint" || HEALTH_FAILED=1

# MCP functionality
echo -e "${YELLOW}🧠 MCP Functionality${NC}"
json_check "/list_tools" "List tools endpoint" || HEALTH_FAILED=1
json_check "/list_resources" "List resources endpoint" || HEALTH_FAILED=1

# Ontology endpoints
echo -e "${YELLOW}🔗 Ontology Endpoints${NC}"
http_check "/ontology/sources" "Ontology sources" || HEALTH_FAILED=1
http_check "/ontology/entities" "Ontology entities" || HEALTH_FAILED=1

# Guidelines functionality
echo -e "${YELLOW}📋 Guidelines Functionality${NC}"
http_check "/guidelines/analyze" "Guidelines analysis" || HEALTH_FAILED=1

# Performance check
echo -e "${YELLOW}⚡ Performance Check${NC}"
echo -n "  Response time... "
START_TIME=$(date +%s%N)
if curl -s -f --connect-timeout 10 "$MCP_URL/health" > /dev/null; then
    END_TIME=$(date +%s%N)
    RESPONSE_TIME=$(( (END_TIME - START_TIME) / 1000000 ))
    
    if [ $RESPONSE_TIME -lt 1000 ]; then
        echo -e "${GREEN}✅ ${RESPONSE_TIME}ms${NC}"
    elif [ $RESPONSE_TIME -lt 3000 ]; then
        echo -e "${YELLOW}⚠️ ${RESPONSE_TIME}ms (slow)${NC}"
    else
        echo -e "${RED}❌ ${RESPONSE_TIME}ms (very slow)${NC}"
        HEALTH_FAILED=1
    fi
else
    echo -e "${RED}❌ No response${NC}"
    HEALTH_FAILED=1
fi

# Server status (for remote environments)
if [[ -n "$SSH_HOST" ]]; then
    echo -e "${YELLOW}🖥️ Server Status${NC}"
    echo -n "  SSH connectivity... "
    if ssh -o ConnectTimeout=5 -o BatchMode=yes "$SSH_USER@$SSH_HOST" exit 2>/dev/null; then
        echo -e "${GREEN}✅ OK${NC}"
        
        # Check process status
        echo -n "  MCP process status... "
        PROCESS_COUNT=$(ssh "$SSH_USER@$SSH_HOST" "pgrep -f 'enhanced_ontology_server_with_guidelines.py' | wc -l")
        if [ "$PROCESS_COUNT" -gt 0 ]; then
            echo -e "${GREEN}✅ Running ($PROCESS_COUNT processes)${NC}"
        else
            echo -e "${RED}❌ Not running${NC}"
            HEALTH_FAILED=1
        fi
        
        # Check system resources
        echo -n "  System load... "
        LOAD_AVG=$(ssh "$SSH_USER@$SSH_HOST" "uptime | awk -F'load average:' '{print \$2}' | awk '{print \$1}' | sed 's/,//'")
        if (( $(echo "$LOAD_AVG < 2.0" | bc -l) )); then
            echo -e "${GREEN}✅ $LOAD_AVG${NC}"
        else
            echo -e "${YELLOW}⚠️ $LOAD_AVG (high)${NC}"
        fi
        
        # Check memory usage
        echo -n "  Memory usage... "
        MEM_USAGE=$(ssh "$SSH_USER@$SSH_HOST" "free | grep Mem | awk '{printf \"%.1f\", \$3/\$2 * 100.0}'")
        if (( $(echo "$MEM_USAGE < 80.0" | bc -l) )); then
            echo -e "${GREEN}✅ ${MEM_USAGE}%${NC}"
        else
            echo -e "${YELLOW}⚠️ ${MEM_USAGE}% (high)${NC}"
        fi
        
    else
        echo -e "${RED}❌ SSH connection failed${NC}"
        HEALTH_FAILED=1
    fi
fi

# Summary
echo
echo -e "${BLUE}📊 Health Check Summary${NC}"
echo -e "${BLUE}=======================${NC}"

if [ $HEALTH_FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed - MCP server is healthy!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some checks failed - MCP server needs attention${NC}"
    
    # Provide troubleshooting tips
    echo
    echo -e "${YELLOW}🔧 Troubleshooting Tips:${NC}"
    echo "1. Check server logs: ssh $SSH_USER@$SSH_HOST 'tail -f /home/chris/proethica/mcp-server/logs/mcp_*.log'"
    echo "2. Restart MCP server: ssh $SSH_USER@$SSH_HOST 'cd /home/chris/proethica/mcp-server/current && pkill -f enhanced_ontology && nohup python enhanced_ontology_server_with_guidelines.py &'"
    echo "3. Check system resources: ssh $SSH_USER@$SSH_HOST 'htop'"
    echo "4. Verify network connectivity: ping $SSH_HOST"
    
    exit 1
fi