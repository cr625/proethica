#!/bin/bash
# This script runs the complete guidelines MCP pipeline
# It starts the MCP server and then runs the test client

# Set up environment variables if needed
if [ -f .env ]; then
    echo "Loading environment variables from .env file..."
    export $(grep -v '^#' .env | xargs)
fi

# Make sure MCP_SERVER_PORT is set, default to 5001
export MCP_SERVER_PORT=${MCP_SERVER_PORT:-5001}
echo "Using MCP server port: ${MCP_SERVER_PORT}"

# Display Anthropic and OpenAI key availability
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "Anthropic API key is available"
else
    echo "WARNING: Anthropic API key is not set. LLM features may not work properly."
fi

if [ -n "$OPENAI_API_KEY" ]; then
    echo "OpenAI API key is available"
else
    echo "Note: OpenAI API key is not set. Will use fallback mode if needed."
fi

# Start the MCP server in the background
echo "Starting the MCP server..."
python mcp/run_enhanced_mcp_server_with_guidelines.py &
MCP_PID=$!

# Check if the server started properly
if [ $? -ne 0 ]; then
    echo "Failed to start MCP server"
    exit 1
fi

echo "MCP server started with PID: $MCP_PID"

# Wait for server to initialize (can be adjusted as needed)
echo "Waiting 5 seconds for server to initialize..."
sleep 5

# Run the test client
echo "Running guideline analysis test client..."
python test_guideline_mcp_client.py

# Capture the result from the client
CLIENT_RESULT=$?

# Kill the server process
echo "Shutting down MCP server (PID: $MCP_PID)..."
kill $MCP_PID

# Wait for server to shut down gracefully
sleep 2

# Check if we need to force kill
if ps -p $MCP_PID > /dev/null; then
    echo "Server still running, forcing shutdown..."
    kill -9 $MCP_PID
fi

echo ""
echo "Pipeline execution complete."
echo "Results saved to guideline_*.json and guideline_triples.ttl files."

# Return the client's exit code
exit $CLIENT_RESULT
