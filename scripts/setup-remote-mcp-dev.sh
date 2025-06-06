#!/bin/bash
# Configure development environment to use remote MCP server

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "======================================"
echo "Remote MCP Server Development Setup"
echo "======================================"
echo ""

# Check for existing .env.development
if [[ -f "$PROJECT_ROOT/.env.development" ]]; then
    echo "⚠️  .env.development already exists"
    read -p "Backup and overwrite? (yes/no): " confirm
    if [[ "$confirm" == "yes" ]]; then
        cp "$PROJECT_ROOT/.env.development" "$PROJECT_ROOT/.env.development.backup.$(date +%Y%m%d_%H%M%S)"
    else
        exit 0
    fi
fi

# Choose connection method
echo "How would you like to connect to the MCP server?"
echo "1) Direct HTTPS connection to mcp.proethica.org"
echo "2) SSH tunnel to production server"
echo "3) Local MCP server (default)"
echo ""
read -p "Select option (1-3): " option

case $option in
    1)
        echo ""
        echo "Setting up direct HTTPS connection..."
        
        # Generate API key if needed
        read -p "Do you have an MCP API key? (yes/no): " has_key
        if [[ "$has_key" != "yes" ]]; then
            echo "Generating new API key..."
            API_KEY=$(openssl rand -hex 32)
            echo "Your API key: $API_KEY"
            echo "⚠️  Save this key! You'll need to add it to the production server."
        else
            read -p "Enter your API key: " API_KEY
        fi
        
        cat > "$PROJECT_ROOT/.env.development" << EOF
# Remote MCP Server Configuration
MCP_SERVER_URL=https://mcp.proethica.org
MCP_API_KEY=$API_KEY
MCP_CONNECTION_MODE=direct

# Flask Development Settings
FLASK_ENV=development
FLASK_DEBUG=1

# Use local database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_ethical_dm

# Keep other services local
REDIS_URL=redis://localhost:6379
EOF
        
        echo ""
        echo "✅ Configured for direct HTTPS connection"
        echo ""
        echo "Next steps:"
        echo "1. Add this API key to production server's allowed keys"
        echo "2. Restart your Flask development server"
        ;;
        
    2)
        echo ""
        echo "Setting up SSH tunnel..."
        
        # Check SSH key
        if [[ ! -f "$HOME/.ssh/proethica-deploy" ]]; then
            echo "❌ SSH key not found at ~/.ssh/proethica-deploy"
            echo "Run: ssh-keygen -t ed25519 -f ~/.ssh/proethica-deploy"
            exit 1
        fi
        
        cat > "$PROJECT_ROOT/.env.development" << EOF
# SSH Tunnel MCP Configuration
MCP_SERVER_URL=http://localhost:5002
MCP_CONNECTION_MODE=ssh_tunnel

# Flask Development Settings
FLASK_ENV=development
FLASK_DEBUG=1

# Use local database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_ethical_dm

# SSH tunnel settings (for reference)
SSH_TUNNEL_HOST=209.38.62.85
SSH_TUNNEL_USER=chris
SSH_TUNNEL_KEY=$HOME/.ssh/proethica-deploy
SSH_TUNNEL_REMOTE_PORT=5002
SSH_TUNNEL_LOCAL_PORT=5002
EOF
        
        # Create SSH tunnel script
        cat > "$PROJECT_ROOT/scripts/start-mcp-tunnel.sh" << 'EOF'
#!/bin/bash
# Start SSH tunnel to remote MCP server

echo "Starting SSH tunnel to MCP server..."
ssh -N -L 5002:localhost:5002 \
    -i ~/.ssh/proethica-deploy \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=3 \
    chris@209.38.62.85 \
    -v

# Use in another terminal or with nohup/screen:
# nohup ./scripts/start-mcp-tunnel.sh > tunnel.log 2>&1 &
EOF
        
        chmod +x "$PROJECT_ROOT/scripts/start-mcp-tunnel.sh"
        
        echo ""
        echo "✅ Configured for SSH tunnel connection"
        echo ""
        echo "To start the tunnel:"
        echo "  ./scripts/start-mcp-tunnel.sh"
        echo ""
        echo "Or run in background:"
        echo "  nohup ./scripts/start-mcp-tunnel.sh > tunnel.log 2>&1 &"
        ;;
        
    3)
        echo ""
        echo "Using local MCP server..."
        
        cat > "$PROJECT_ROOT/.env.development" << EOF
# Local MCP Server Configuration
MCP_SERVER_URL=http://localhost:5001
MCP_CONNECTION_MODE=local

# Flask Development Settings
FLASK_ENV=development
FLASK_DEBUG=1

# Use local database
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/ai_ethical_dm

# Local services
REDIS_URL=redis://localhost:6379
EOF
        
        echo ""
        echo "✅ Configured for local MCP server"
        ;;
        
    *)
        echo "Invalid option"
        exit 1
        ;;
esac

# Create VS Code settings for remote development
mkdir -p "$PROJECT_ROOT/.vscode"
cat > "$PROJECT_ROOT/.vscode/settings.json" << EOF
{
    "python.envFile": "\${workspaceFolder}/.env.development",
    "terminal.integrated.env.linux": {
        "MCP_SERVER_URL": "\${env:MCP_SERVER_URL}"
    },
    "remote.SSH.defaultForwardedPorts": [
        {
            "name": "MCP Server",
            "localPort": 5002,
            "remotePort": 5002
        },
        {
            "name": "Flask App",
            "localPort": 5000,
            "remotePort": 5000
        }
    ]
}
EOF

# Create launch configuration
cat > "$PROJECT_ROOT/.vscode/launch.json" << EOF
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "Flask with Remote MCP",
            "type": "python",
            "request": "launch",
            "module": "flask",
            "env": {
                "FLASK_APP": "run.py",
                "FLASK_ENV": "development"
            },
            "args": [
                "run",
                "--host=0.0.0.0",
                "--port=5000"
            ],
            "jinja": true,
            "envFile": "\${workspaceFolder}/.env.development"
        }
    ]
}
EOF

echo ""
echo "Additional setup completed:"
echo "✅ Created .env.development"
echo "✅ Created VS Code settings"
echo "✅ Created VS Code launch configuration"
echo ""
echo "To use this configuration:"
echo "1. Source the environment: source .env.development"
echo "2. Or use VS Code's Python extension to auto-load"
echo "3. Start Flask with: flask run"