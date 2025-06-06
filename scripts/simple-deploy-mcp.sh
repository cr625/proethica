#!/bin/bash
# Simple MCP deployment script for testing

set -e

echo "🚀 Simple MCP Server Deployment"
echo "==============================="

# Configuration
SERVER_HOST="209.38.62.85"
SERVER_USER="chris"
SSH_KEY="$HOME/.ssh/proethica-deploy"

echo "📦 Updating repository on server..."
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_HOST" << 'EOF'
    cd /home/chris/proethica-repo
    git fetch origin
    git checkout develop
    git pull origin develop
    echo "✅ Repository updated"
    
    # Copy updated MCP files to the running MCP directory
    echo "Copying updated MCP files..."
    cp -r /home/chris/proethica-repo/mcp/* /home/chris/proethica-mcp/mcp/
    echo "✅ MCP files updated"
EOF

echo "🔄 Restarting MCP server..."
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_HOST" << 'EOF'
    # Find and kill existing MCP process
    MCP_PID=$(pgrep -f "mcp/http_ontology_mcp_server.py" || echo "")
    if [ -n "$MCP_PID" ]; then
        echo "Stopping MCP process $MCP_PID..."
        kill $MCP_PID
        sleep 3
        
        # Force kill if still running
        if kill -0 $MCP_PID 2>/dev/null; then
            echo "Force killing MCP process..."
            kill -9 $MCP_PID
            sleep 2
        fi
    fi
    
    # Restart MCP service using systemd (with passwordless sudo)
    echo "Restarting MCP service..."
    sudo systemctl restart proethica-mcp-home.service
    
    # Wait for startup
    sleep 5
    
    # Check if new process is running
    NEW_PID=$(pgrep -f "mcp/http_ontology_mcp_server.py" || echo "")
    if [ -n "$NEW_PID" ]; then
        echo "✅ MCP server restarted successfully (PID: $NEW_PID)"
    else
        echo "❌ MCP server restart failed"
        echo "Last log entries:"
        tail -10 /tmp/mcp-server.log
        exit 1
    fi
EOF

echo "🏥 Testing MCP server health..."
sleep 2
if curl -s https://mcp.proethica.org/health | grep -q "ok"; then
    echo "✅ MCP server is healthy"
    echo "🎉 Deployment completed successfully!"
else
    echo "❌ MCP server health check failed"
    exit 1
fi