#!/usr/bin/env python3
"""
Simplified Debug Application for ProEthica Codespace

This application provides a minimal debug interface for the ProEthica system
running in a GitHub Codespace environment. It avoids template issues by using
simple string responses.
"""

import os
import sys
import json
import logging
import requests
from flask import Flask, jsonify
import psycopg2

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Create Flask application
app = Flask(__name__)

# Configuration
MCP_SERVER_URL = os.environ.get('MCP_SERVER_URL', 'http://localhost:5001/jsonrpc')
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5433/ai_ethical_dm')

# Global state
db_connected = False
db_version = "Unknown"
mcp_connected = False
mcp_tools = []

def check_database():
    """Check database connection"""
    global db_connected, db_version
    try:
        logger.info(f"Testing connection to database: {DATABASE_URL}")
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        db_version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        db_connected = True
        logger.info(f"Successfully connected to database. Version: {db_version}")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to database: {str(e)}")
        db_connected = False
        return False

def check_mcp_server():
    """Check MCP server connection"""
    global mcp_connected, mcp_tools
    try:
        logger.info(f"Testing connection to MCP server at {MCP_SERVER_URL}")
        payload = {
            "jsonrpc": "2.0",
            "method": "list_tools",
            "params": {},
            "id": 1
        }
        response = requests.post(MCP_SERVER_URL, json=payload, timeout=5)
        response.raise_for_status()
        data = response.json()
        mcp_tools = data.get('result', {}).get('tools', [])
        mcp_connected = True
        logger.info("Successfully connected to MCP server!")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to MCP server: {str(e)}")
        mcp_connected = False
        return False

@app.route('/')
def index():
    """Debug index route - plain text for simplicity"""
    global db_connected, mcp_connected, mcp_tools, db_version
    
    # Check connections
    db_status = check_database()
    mcp_status = check_mcp_server()
    
    # Build a simple plain text response
    response = [
        "=== ProEthica Codespace Debug Interface ===",
        "",
        "--- System Status ---",
        f"Database: {'Connected' if db_connected else 'Disconnected'}",
        f"Database Version: {db_version if db_connected else 'N/A'}",
        f"MCP Server: {'Connected' if mcp_connected else 'Disconnected'}",
        f"MCP Tools: {len(mcp_tools)} available",
        "",
    ]
    
    # Add MCP tools info if connected
    if mcp_connected:
        response.append("--- Available MCP Tools ---")
        for tool in mcp_tools:
            response.append(f"* {tool.get('name')}: {tool.get('description')}")
        response.append("")
    
    # Add environment info
    response.append("--- Environment Information ---")
    for key in ['FLASK_APP', 'FLASK_ENV', 'DATABASE_URL', 'MCP_SERVER_URL']:
        response.append(f"{key}: {os.environ.get(key, 'Not set')}")
    response.append("")
    
    # Simple text response - no templates required
    return "<pre>" + "\n".join(response) + "</pre>"

@app.route('/api/status')
def api_status():
    """API endpoint for status as JSON"""
    check_database()
    check_mcp_server()
    
    status = {
        'database': {
            'connected': db_connected,
            'version': db_version if db_connected else None
        },
        'mcp_server': {
            'connected': mcp_connected,
            'url': MCP_SERVER_URL,
            'tools_count': len(mcp_tools)
        },
        'environment': {
            'flask_app': os.environ.get('FLASK_APP'),
            'flask_env': os.environ.get('FLASK_ENV')
        }
    }
    
    return jsonify(status)

if __name__ == "__main__":
    # Initialize by checking connections
    check_database()
    check_mcp_server()
    
    # Start the Flask application
    app.run(host='0.0.0.0', port=5050, debug=True)
