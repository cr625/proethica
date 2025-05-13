#!/usr/bin/env python3
"""
Simple debug launcher for the Codespace environment
This file tests configurations and starts a basic Flask server
"""

import os
import sys
import json
import requests
import logging
import datetime
from flask import Flask, render_template
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add MCP path for direct imports
mcp_path = os.path.join(os.path.dirname(__file__), 'mcp')
if mcp_path not in sys.path:
    sys.path.append(mcp_path)

# Ensure logs directory exists
logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(logs_dir, exist_ok=True)

# Set environment variables
os.environ['FLASK_APP'] = 'codespace_run.py'
os.environ['FLASK_ENV'] = 'development'
os.environ['FLASK_DEBUG'] = '1'
os.environ['DATABASE_URL'] = 'postgresql://postgres:postgres@localhost:5433/ai_ethical_dm'
os.environ['ENVIRONMENT'] = 'codespace'

# Test MCP server connection
def test_mcp_connection(url):
    """Test connection to the MCP server"""
    logger.info(f"Testing connection to MCP server at {url}...")
    try:
        response = requests.post(
            url,
            json={
                "jsonrpc": "2.0",
                "method": "list_tools",
                "params": {},
                "id": 1
            },
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        
        if "result" in data:
            logger.info("Successfully connected to MCP server!")
            return True, data["result"]
        else:
            logger.error(f"Error response from MCP server: {data}")
            return False, None
    except Exception as e:
        logger.error(f"Failed to connect to MCP server: {e}")
        return False, None

# Test database connection
def test_db_connection(db_url):
    """Test connection to the PostgreSQL database"""
    try:
        import psycopg2
        logger.info(f"Testing connection to database: {db_url}")
        connection = psycopg2.connect(db_url)
        cursor = connection.cursor()
        cursor.execute('SELECT version();')
        db_version = cursor.fetchone()
        cursor.close()
        connection.close()
        logger.info(f"Successfully connected to database. Version: {db_version[0]}")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return False

def create_app():
    """Create a simple Flask app for debugging"""
    app = Flask(__name__)
    
    # Configure the app
    app.config['SECRET_KEY'] = 'debug-key-for-codespace'
    app.config['DEBUG'] = True
    
    @app.route('/')
    def index():
        return render_template('debug/codespace_index.html', 
                               title="Codespace Debug",
                               data={
                                   "timestamp": datetime.datetime.now().isoformat(),
                                   "environment": os.environ.get('ENVIRONMENT', 'unknown'),
                                   "db_url": os.environ.get('DATABASE_URL', 'not set')
                               })
    
    @app.route('/test')
    def test():
        return render_template('debug/test.html', title="Test Page")
    
    return app

if __name__ == '__main__':
    logger.info("Starting Codespace debug environment")
    
    # Set MCP server URL
    mcp_server_url = os.environ.get('MCP_SERVER_URL', 'http://localhost:5001/jsonrpc')
    logger.info(f"Set MCP_SERVER_URL to {mcp_server_url}")
    
    # Check MCP server status
    logger.info("Checking MCP server status...")
    mcp_connected, tools = test_mcp_connection(mcp_server_url)
    
    # Check database connection
    db_connected = test_db_connection(os.environ['DATABASE_URL'])
    
    if not mcp_connected:
        logger.warning("MCP server not connected! Some features will not work.")
    else:
        # Check for guideline tools
        guideline_tools = [t for t in tools if "guideline" in t]
        logger.info(f"Found guideline tools: {', '.join(guideline_tools)}")
    
    if not db_connected:
        logger.warning("Database not connected! Application will not work correctly.")
        
    # Create and run the Flask app
    app = create_app()
    app.run(host='0.0.0.0', port=5050, debug=True)
