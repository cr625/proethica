#!/bin/bash
#
# Enhanced Ontology-LLM Integration Demo Script
# This script demonstrates the enhanced ontology integration with LLM via MCP
#

# Set script to exit on error
set -e

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Print header
echo "🚀 Enhanced Ontology-LLM Integration Demo"
echo "========================================"
echo ""

# Check environment
if [ ! -f ".env" ]; then
    echo "❌ .env file not found!"
    echo "   Create .env file with required environment variables"
    exit 1
fi

source .env

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "⚠️ ANTHROPIC_API_KEY not set in .env file"
    echo "  Demo will use mock responses instead of real Claude responses"
    export USE_MOCK_FALLBACK=true
else
    echo "✅ ANTHROPIC_API_KEY found"
    export USE_MOCK_FALLBACK=false
fi

# Check for required enhanced MCP scripts
if [ ! -f "mcp/run_enhanced_mcp_server.py" ]; then
    echo "ℹ️ Enhanced MCP server script not found, running setup..."
    python "$SCRIPT_DIR/enable_enhanced_ontology_integration.py"
fi

# Check if MCP server is already running
if pgrep -f "python.*mcp/run_enhanced_mcp_server.py" > /dev/null; then
    echo "✅ Enhanced MCP server is already running"
else
    echo "🚀 Starting Enhanced MCP server..."
    python mcp/run_enhanced_mcp_server.py --load-db &
    MCP_PID=$!
    echo "   MCP server started with PID $MCP_PID"
    # Wait for server to start
    echo "⏳ Waiting for server to start..."
    sleep 3
    
    # Verify server is running
    if kill -0 $MCP_PID 2>/dev/null; then
        echo "✅ MCP server started successfully"
    else
        echo "❌ Failed to start MCP server"
        exit 1
    fi
fi

# Run tests to verify integration
echo ""
echo "🧪 Running integration tests..."
python "$SCRIPT_DIR/test_enhanced_ontology_integration.py"
TEST_RESULT=$?

if [ $TEST_RESULT -eq 0 ]; then
    echo ""
    echo "🎉 Enhanced Ontology-LLM Integration is working!"
    echo ""
    echo "🌐 Starting ProEthica with enhanced ontology integration..."
    echo "   Use the Ontology Agent to interact with the ontology via Claude."
    echo "   The application will be available at http://localhost:3333/"
    echo ""
    echo "   To stop, press Ctrl+C"
    echo ""
    
    # Start the application
    python run.py
else
    echo ""
    echo "❌ Integration tests failed"
    echo "   Please check the logs for details"
    exit 1
fi
