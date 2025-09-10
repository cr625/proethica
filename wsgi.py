#!/usr/bin/env python
"""
WSGI entry point for ProEthica Flask Application
Used for production deployments with WSGI servers like Gunicorn or uWSGI
"""

import os
import sys
import socket
import logging
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_mcp_server(host='localhost', port=8082):
    """Check if OntServe MCP server is running."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

# Check OntServe MCP Server availability
mcp_port = int(os.environ.get('ONTSERVE_MCP_PORT', 8082))
mcp_host = os.environ.get('ONTSERVE_MCP_HOST', 'localhost')

if check_mcp_server(host=mcp_host, port=mcp_port):
    logger.info(f"✓ OntServe MCP server detected at {mcp_host}:{mcp_port}")
    os.environ['ONTSERVE_MCP_ENABLED'] = 'true'
    os.environ['ONTSERVE_MCP_URL'] = f'http://{mcp_host}:{mcp_port}'
else:
    logger.warning(f"⚠ OntServe MCP server not detected at {mcp_host}:{mcp_port}")
    logger.warning("ProEthica will run with limited functionality.")
    logger.warning("For production, ensure MCP server is started via systemd or supervisor.")
    os.environ['ONTSERVE_MCP_ENABLED'] = 'false'

# Import the Flask app factory
from app import create_app

# Create the Flask application instance
try:
    app = create_app()
    logger.info("ProEthica Flask application initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize ProEthica application: {e}")
    raise

# This is the WSGI application object that servers will use
application = app

if __name__ == '__main__':
    # This block only runs if the script is executed directly
    # For development/testing purposes
    logger.warning("Running wsgi.py directly is not recommended for production")
    logger.info("Use 'gunicorn wsgi:application' or similar WSGI server instead")
    app.run(debug=True)
