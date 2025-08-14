#!/bin/bash
# Load environment variables from .env file
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
  echo "Loaded environment variables from .env file"
  
  # Verify that key variables are present
  if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo "✓ ANTHROPIC_API_KEY is set"
  else
    echo "⚠ WARNING: ANTHROPIC_API_KEY is not set in .env file"
  fi
  
  if [ -n "$OPENAI_API_KEY" ]; then
    echo "✓ OPENAI_API_KEY is set"
  fi
else
  echo "Warning: .env file not found"
fi

# Set USE_MOCK_GUIDELINE_RESPONSES to false explicitly
export USE_MOCK_GUIDELINE_RESPONSES=false
echo "Setting USE_MOCK_GUIDELINE_RESPONSES=false"

# Start the MCP server using the project virtualenv if available
echo "Starting MCP server with environment variables..."
VENV_PY="$(pwd)/venv/bin/python"
if [ -x "$VENV_PY" ]; then
  echo "Using venv Python: $VENV_PY"
  "$VENV_PY" mcp/run_enhanced_mcp_server_with_guidelines.py
else
  echo "Venv Python not found; falling back to system python"
  python mcp/run_enhanced_mcp_server_with_guidelines.py
fi
