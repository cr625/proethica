#!/usr/bin/env python3
"""
Special entry point for running the Flask app in GitHub Codespace environment.
This version handles the specific configuration needed in Codespaces.
"""

import os
import logging
import argparse
import requests
import time
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file if it exists
if os.path.exists('.env'):
    load_dotenv()

# Parse command-line arguments
parser = argparse.ArgumentParser(description='Run the AI Ethical DM application in GitHub Codespaces')
parser.add_argument('--port', type=int, default=3333, help='Port to run the server on')
parser.add_argument('--mcp-port', type=int, default=5001, help='Port for the MCP server')
args = parser.parse_args()

# Set Codespace-specific environment variables
os.environ['ENVIRONMENT'] = 'app.config.CodespaceConfig'
os.environ['CODESPACE'] = 'true'
os.environ['FLASK_ENV'] = 'development'
os.environ['FLASK_DEBUG'] = '1'

# Set MCP server URL
mcp_port = args.mcp_port
mcp_url = f"http://localhost:{mcp_port}"
os.environ['MCP_SERVER_URL'] = mcp_url
logger.info(f"Set MCP_SERVER_URL to {mcp_url}")

# Check MCP server status
logger.info("Checking MCP server status...")
mcp_running = False
try:
    test_url = f"{mcp_url}/jsonrpc"
    logger.info(f"Testing connection to MCP server at {test_url}...")
    response = requests.post(
        test_url, 
        json={
            "jsonrpc": "2.0",
            "method": "list_tools",
            "params": {},
            "id": 1
        },
        timeout=2
    )
    if response.status_code == 200:
        mcp_running = True
        logger.info("Successfully connected to MCP server!")
        tools = response.json().get("result", {}).get("tools", [])
        guideline_tools = [t for t in tools if "guideline" in t.get("name", "").lower()]
        if guideline_tools:
            logger.info(f"Found guideline tools: {', '.join(t['name'] for t in guideline_tools)}")
        else:
            logger.warning("No guideline tools found in the MCP server!")
    else:
        logger.warning(f"MCP server returned status code {response.status_code}")
except requests.exceptions.RequestException as e:
    logger.error(f"Could not connect to MCP server: {e}")
    
if not mcp_running:
    logger.warning("MCP server may not be running properly. Continuing anyway...")
    logger.info("Please ensure the MCP server is running: python mcp/run_enhanced_mcp_server_with_guidelines.py")

# Import app creation function after env vars are set
from app import create_app

# Create app instance with the Codespace config
app = create_app()

if __name__ == '__main__':
    logger.info(f"Starting Flask server on port {args.port}...")
    app.run(host='0.0.0.0', port=args.port, debug=True)
