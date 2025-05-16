#!/usr/bin/env python
"""
Python wrapper for debug_app.sh to allow proper debugging with VSCode
"""
import os
import subprocess
import sys
import argparse

def main():
    print("Applying SQLAlchemy URL fix patch...")
    subprocess.run(["python", "patch_sqlalchemy_url.py"], check=True)

    print("Setting environment variables...")
    os.environ["ENVIRONMENT"] = "codespace"
    os.environ["DATABASE_URL"] = "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
    os.environ["SQLALCHEMY_DATABASE_URI"] = "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
    os.environ["MCP_SERVER_URL"] = "http://localhost:5001"
    os.environ["MCP_SERVER_ALREADY_RUNNING"] = "true"
    os.environ["FLASK_DEBUG"] = "1"
    os.environ["USE_MOCK_GUIDELINE_RESPONSES"] = "true"

    print("Running application...")
    
    # Add the current directory to path so imports work properly
    sys.path.insert(0, os.getcwd())
    
    # Import modules from run.py
    from dotenv import load_dotenv
    from app import create_app
    import requests
    
    # Load environment variables from .env file if it exists
    if os.path.exists('.env'):
        load_dotenv()
    
    # Set port and MCP port
    port = 3333
    mcp_port = 5001
    
    # Set environment variables similar to run.py
    os.environ['MCP_SERVER_PORT'] = str(mcp_port)
    mcp_url = f"http://localhost:{mcp_port}"
    os.environ['MCP_SERVER_URL'] = mcp_url
    print(f"Set MCP_SERVER_URL to {mcp_url}")
    
    # Log a clear message about MCP server port configuration
    print(f"MCP server should be available at {mcp_url}")
    
    # Verify that the MCP server is already running
    mcp_running = False
    try:
        test_url = f"http://localhost:{mcp_port}"
        print(f"Testing connection to MCP server at {test_url}...")
        response = requests.get(test_url, timeout=2)
        if response.status_code == 200:
            mcp_running = True
            print("Successfully connected to existing MCP server!")
        else:
            print(f"Warning: MCP server returned status code {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Warning: Could not connect to MCP server: {e}")
        
    if not mcp_running:
        print("WARNING: MCP server may not be running properly. Continuing anyway...")
    
    # Create app instance with the proper configuration module
    app = create_app('config')
    
    print(f"Starting Flask server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)

if __name__ == "__main__":
    main()
