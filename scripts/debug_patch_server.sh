#!/bin/bash
# Script to patch MCP server for enhanced debugging

# Set directory variables
SCRIPT_DIR=$(dirname "$0")
MCP_DIR="${SCRIPT_DIR}/mcp"
ENHANCED_SERVER="${MCP_DIR}/enhanced_ontology_server_with_guidelines.py"
HTTP_SERVER="${MCP_DIR}/http_ontology_mcp_server.py"

# Display banner
echo "===================================="
echo " MCP Server Debug Patch Utility"
echo "===================================="
echo "This script will add enhanced debugging to the MCP server"

# Check if files exist
if [ ! -f "$ENHANCED_SERVER" ]; then
    echo "Error: Enhanced ontology server not found at ${ENHANCED_SERVER}"
    exit 1
fi

if [ ! -f "$HTTP_SERVER" ]; then
    echo "Error: HTTP ontology server not found at ${HTTP_SERVER}"
    exit 1
fi

# Create backup copies
echo "Creating backup copies of server files..."
cp "$ENHANCED_SERVER" "${ENHANCED_SERVER}.bak"
cp "$HTTP_SERVER" "${HTTP_SERVER}.bak"

echo "✅ Backups created"

# Add import for enhanced debug logging to enhanced server
echo "Patching enhanced server with debug logging imports..."
sed -i '1,20s/import logging/import logging\nfrom mcp.enhanced_debug_logging import log_debug_point, log_json_rpc_request, log_method_call/' "$ENHANCED_SERVER"

# Add debug logging to handle_jsonrpc method
echo "Adding debug logging to handle_jsonrpc method..."
sed -i '/async def handle_jsonrpc/,/try:/ s/try:/try:\n            # Log the incoming request for debugging\n            request_data = await request.json()\n            log_json_rpc_request(request_data)\n            log_debug_point(message="Processing JSON-RPC request")/' "$ENHANCED_SERVER"

# Add debug logging to _handle_call_tool method
echo "Adding debug logging to _handle_call_tool method..."
sed -i '/async def _handle_call_tool/,/name = params\.get/ s/name = params\.get/log_debug_point(message="Handling tool call")\n        name = params\.get/' "$ENHANCED_SERVER"

# Make the patch script executable
chmod +x "$SCRIPT_DIR/debug_app.sh"

echo "===================================="
echo "✅ Debug patches applied!"
echo "===================================="
echo
echo "To use the enhanced debugging:"
echo "1. Run './debug_app.sh' to start the application"
echo "2. Set MCP_DEBUG=true before starting the MCP server"
echo "3. Watch the console output for detailed debug logs"
echo
echo "The debug logs will show you exactly where the code is executing,"
echo "even if the VSCode breakpoints aren't triggering properly."
echo "===================================="
