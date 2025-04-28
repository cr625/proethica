#!/bin/bash
#
# Script to update auto_run.sh to use the enhanced MCP server integration
# This allows for seamless transition to the enhanced ontology-LLM integration
#

# Set script to exit on error
set -e

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

echo "📝 Updating auto_run.sh for enhanced MCP integration"
echo "==================================================="

# Check if auto_run.sh exists
if [ ! -f "auto_run.sh" ]; then
    echo "❌ auto_run.sh not found in project root!"
    exit 1
fi

# Create backup of original script
BACKUP_FILE="auto_run.sh.bak.$(date +%Y%m%d_%H%M%S)"
echo "📦 Creating backup of auto_run.sh as $BACKUP_FILE"
cp auto_run.sh "$BACKUP_FILE"

# New content for auto_run.sh
NEW_CONTENT=$(cat <<'EOF'
#!/bin/bash
#
# Auto-run script for ProEthica with Enhanced MCP Integration
# This script starts both the Enhanced MCP server and the main application
#

# Load environment variables
source .env

# Check for required environment variables
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️ ANTHROPIC_API_KEY not set in .env file"
    echo "  Setting USE_MOCK_FALLBACK=true"
    export USE_MOCK_FALLBACK=true
else
    echo "✅ ANTHROPIC_API_KEY found"
fi

echo "Running in DEVELOPMENT mode"
export FLASK_ENV=development

# Set MCP server URL
export MCP_SERVER_URL=http://localhost:5001

# Start Enhanced MCP server if not already running
if pgrep -f "python.*mcp/run_enhanced_mcp_server.py" > /dev/null; then
    echo "Enhanced MCP server already running"
else
    echo "Starting Enhanced MCP server..."
    echo "MCP server will be available at $MCP_SERVER_URL"
    python mcp/run_enhanced_mcp_server.py --load-db &
    # Store the PID of the MCP server
    MCP_PID=$!
    echo "MCP server started with PID $MCP_PID"
    # Wait a moment for the server to start
    sleep 2
    # Check if the server started successfully
    if kill -0 $MCP_PID 2>/dev/null; then
        echo "Successfully connected to MCP server!"
    else
        echo "⚠️ Failed to start MCP server"
        echo "  Setting USE_MOCK_FALLBACK=true"
        export USE_MOCK_FALLBACK=true
    fi
fi

# Start the main application
echo "Starting application in DEVELOPMENT mode"
python run.py

# Optional cleanup on exit
# trap 'pkill -f "python.*mcp/run_enhanced_mcp_server.py"' EXIT
EOF
)

# Write the new content
echo "$NEW_CONTENT" > auto_run.sh

# Make the script executable
chmod +x auto_run.sh

echo "✅ auto_run.sh has been updated to use the Enhanced MCP Server"
echo ""
echo "ℹ️ To use the standard MCP server instead, run:"
echo "   ./scripts/restart_mcp_server.sh"
echo ""
echo "ℹ️ To start ProEthica with enhanced ontology integration, run:"
echo "   ./auto_run.sh"
