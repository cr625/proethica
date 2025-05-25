# Anthropic SDK Environment Variables Fix

## Problem Overview

When accessing the codespace from a different computer, the guideline concept extraction process began returning errors:

```
2025-05-20 00:33:11,735 - app.routes.worlds - ERROR - Guideline processing error: Concept Extraction Error - Error extracting concepts: LLM client not available
```

The MCP server logs revealed the root cause:

```
2025-05-20 00:32:40,599 - __main__ - WARNING - ANTHROPIC_API_KEY not found in environment - LLM calls may fail
2025-05-20 00:32:40,600 - mcp.enhanced_ontology_server_with_guidelines - WARNING - ANTHROPIC_API_KEY not found in environment. Anthropic client not available.
```

## Investigation

After analyzing the logs and configuration files, we determined:

1. The `.env` file correctly contained the `ANTHROPIC_API_KEY`.
2. The Flask app was successfully loading environment variables from `.env`.
3. The MCP server was starting but not receiving the environment variables from `.env`.
4. The issue was in how VS Code's `tasks.json` launches the MCP server through the preLaunch task.

## Solution Implemented

We created a helper shell script to properly source the `.env` file before starting the MCP server:

1. Created `start_mcp_server_with_env.sh`:
   ```bash
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
   else
     echo "Warning: .env file not found"
   fi

   # Set USE_MOCK_GUIDELINE_RESPONSES to false explicitly
   export USE_MOCK_GUIDELINE_RESPONSES=false
   
   # Start the MCP server
   echo "Starting MCP server with environment variables..."
   python mcp/run_enhanced_mcp_server_with_guidelines.py
   ```

2. Updated `.vscode/tasks.json` to use this script:
   ```json
   {
       "label": "Start MCP Server with Live LLM",
       "type": "shell",
       "command": "./start_mcp_server_with_env.sh",
       "args": [],
       // ...rest of the configuration remains unchanged
   }
   ```

## Manual Alternative Solution

If the automated solution ever fails, you can manually export the environment variables before starting the MCP server:

```bash
export $(grep -v '^#' .env | xargs)
python mcp/run_enhanced_mcp_server_with_guidelines.py
```

## Root Cause Analysis

The issue was that in VS Code, child processes started through tasks.json don't automatically inherit environment variables from the parent process or from the `.env` file unless explicitly configured to do so. This became apparent when accessing the codespace from a different computer, as the previous configuration might have had the environment variables set up differently.

By using a shell script that explicitly sources the `.env` file, we ensure that the MCP server has access to all the necessary API keys regardless of the host environment.
