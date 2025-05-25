#!/bin/bash
# Debug script for MCP server setup and debugging

# Function to check if a process is running on a port
check_port() {
  local port=$1
  netstat -tuln | grep ":$port " > /dev/null 2>&1
  return $?
}

# Stop any existing MCP server
echo "Checking for existing MCP server processes..."
pkill -f "enhanced_ontology_server_with_guidelines.py" 2>/dev/null
pkill -f "run_enhanced_mcp_server_with_guidelines.py" 2>/dev/null

# Wait a moment to ensure processes are stopped
sleep 2

# Check if port 5001 is still in use
if check_port 5001; then
  echo "Warning: Port 5001 is still in use. Another process might be running on it."
  echo "Try to manually kill it before proceeding."
else
  echo "Port 5001 is available for the MCP server."
fi

# Set environment variables for debugging
export MCP_DEBUG=true
export ANTHROPIC_API_KEY=$(grep ANTHROPIC_API_KEY .env | cut -d '=' -f2)
export OPENAI_API_KEY=$(grep OPENAI_API_KEY .env | cut -d '=' -f2)

# Instructions for debugging
echo
echo "---------------------------------"
echo "MCP SERVER DEBUGGING INSTRUCTIONS"
echo "---------------------------------"
echo
echo "1. Set breakpoints in these locations:"
echo "   - mcp/enhanced_ontology_server_with_guidelines.py: handle_jsonrpc method"
echo "   - mcp/enhanced_ontology_server_with_guidelines.py: _handle_call_tool method"
echo "   - mcp/modules/guideline_analysis_module.py: extract_guideline_concepts method"
echo
echo "2. Start the MCP server in debug mode:"
echo "   - Go to VSCode Run and Debug panel"
echo "   - Select 'Debug Enhanced MCP Server with Guidelines' from dropdown" 
echo "   - Click Play button"
echo
echo "3. Run the application in a separate terminal:"
echo "   ./debug_run.py --port 3333 --mcp-port 5001"
echo
echo "4. Open the browser and navigate to:"
echo "   http://localhost:3333"
echo
echo "5. Go to a guideline and click 'Analyze Concepts' to trigger a debug session"
echo
echo "Environment ready for debugging!"
echo

# End of script
