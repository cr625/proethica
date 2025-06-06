#!/bin/bash
# Restore MCP server to expected location

set -e

echo "🔧 Restoring MCP Server"
echo "======================"

SERVER_HOST="209.38.62.85"
SERVER_USER="chris"
SSH_KEY="$HOME/.ssh/proethica-deploy"

echo "📁 Creating MCP directory structure..."
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_HOST" << 'EOF'
    # Create the expected directory structure
    mkdir -p /home/chris/proethica-mcp/{mcp,logs}
    
    # Copy MCP files from repository
    echo "Copying MCP files..."
    cp -r /home/chris/proethica-repo/mcp/* /home/chris/proethica-mcp/mcp/
    
    # Copy requirements
    cp /home/chris/proethica-repo/requirements-mcp.txt /home/chris/proethica-mcp/
    
    echo "✅ Directory structure created"
EOF

echo "🐍 Setting up Python virtual environment..."
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_HOST" << 'EOF'
    cd /home/chris/proethica-mcp
    
    # Create virtual environment
    python3 -m venv mcp-venv
    
    # Install dependencies
    ./mcp-venv/bin/pip install --upgrade pip
    ./mcp-venv/bin/pip install -r requirements-mcp.txt
    
    echo "✅ Virtual environment created"
EOF

echo "⚙️ Creating environment file..."
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_HOST" << 'EOF'
    cd /home/chris/proethica-mcp
    
    # Create basic environment file
    cat > mcp.env << 'ENVEOF'
# MCP Server Environment
PORT=5002
HOST=0.0.0.0
USE_MOCK_GUIDELINE_RESPONSES=false
PYTHONPATH=/home/chris/proethica-mcp
LOG_LEVEL=INFO
ENVEOF
    
    echo "✅ Environment file created"
EOF

echo "🚀 Starting MCP server via systemd..."
ssh -i "$SSH_KEY" "$SERVER_USER@$SERVER_HOST" << 'EOF'
    # Reload systemd and start service
    sudo systemctl daemon-reload
    sudo systemctl start proethica-mcp-home.service
    
    # Wait for startup
    sleep 5
    
    # Check status
    if systemctl is-active --quiet proethica-mcp-home.service; then
        echo "✅ MCP service started successfully"
        systemctl status proethica-mcp-home.service --no-pager
    else
        echo "❌ MCP service failed to start"
        systemctl status proethica-mcp-home.service --no-pager
        echo "--- Service logs ---"
        journalctl -u proethica-mcp-home.service --no-pager -n 20
        exit 1
    fi
EOF

echo "🏥 Testing MCP server health..."
sleep 3
for i in {1..10}; do
    if curl -s https://mcp.proethica.org/health | grep -q "ok"; then
        echo "✅ MCP server is healthy!"
        echo "🎉 MCP server restoration completed successfully!"
        exit 0
    fi
    echo "Waiting for MCP server... (attempt $i/10)"
    sleep 2
done

echo "❌ MCP server health check failed after 10 attempts"
exit 1