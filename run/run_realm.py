#!/usr/bin/env python3
"""
REALM Application Runner.

This script starts the REALM (Resource for Engineering And Learning Materials) application,
which integrates the Materials Science Engineering Ontology via MCP.
"""

import os
import sys
import logging
import argparse
from pathlib import Path
import time
import json
from threading import Thread
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("realm")

# Import Flask
try:
    from flask import Flask, render_template, request, jsonify, session
except ImportError:
    logger.error("Flask is required. Install it with: pip install flask")
    sys.exit(1)

# Import MCP client
try:
    from mcp_client import MCPClient
except ImportError:
    logger.error("MCP client is required. Install it with: pip install mcp-client")
    sys.exit(1)

# Import REALM and MSEO modules
from realm.services import mseo_service, material_service
from realm.routes import register_routes

def parse_args():
    """Parse command-line arguments.
    
    Returns:
        Parsed arguments
    """
    parser = argparse.ArgumentParser(description="Run the REALM application")
    
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host to bind the server to (default: localhost)"
    )
    
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to run the server on (default: 5000)"
    )
    
    parser.add_argument(
        "--mseo-server",
        type=str,
        default="http://localhost:8078",
        help="URL of the MSEO MCP server (default: http://localhost:8078)"
    )
    
    parser.add_argument(
        "--auto-start-mseo",
        action="store_true",
        help="Automatically start the MSEO MCP server if not running"
    )
    
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode"
    )
    
    return parser.parse_args()

def is_mseo_server_running(url):
    """Check if the MSEO MCP server is running.
    
    Args:
        url: URL of the MSEO MCP server
        
    Returns:
        True if the server is running, False otherwise
    """
    try:
        import requests
        response = requests.get(f"{url}/servers")
        if response.status_code == 200:
            servers = response.json()
            for server in servers:
                if server.get("name") == "mseo-mcp-server":
                    logger.info("MSEO MCP server is running")
                    return True
        
        logger.info("MSEO MCP server is not running")
        return False
    except Exception:
        logger.info("MSEO MCP server is not reachable")
        return False

def start_mseo_server():
    """Start the MSEO MCP server in a separate process.
    
    Returns:
        The server process
    """
    logger.info("Starting MSEO MCP server...")
    
    # Find the run_mseo_mcp_server.py script
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mcp", "mseo", "run_mseo_mcp_server.py")
    
    if not os.path.exists(script_path):
        logger.error(f"MSEO MCP server script not found: {script_path}")
        return None
    
    # Start the server process
    try:
        process = subprocess.Popen(
            [sys.executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        # Wait for server to start
        time.sleep(2)
        
        if process.poll() is not None:
            # Process exited
            stdout, stderr = process.communicate()
            logger.error(f"MSEO MCP server failed to start: {stderr}")
            return None
        
        logger.info("MSEO MCP server started")
        return process
        
    except Exception as e:
        logger.error(f"Error starting MSEO MCP server: {e}")
        return None

def create_app(mseo_server_url):
    """Create and configure the REALM Flask application.
    
    Args:
        mseo_server_url: URL of the MSEO MCP server
        
    Returns:
        Flask application
    """
    # Create Flask app
    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "realm", "templates"),
        static_folder=os.path.join(os.path.dirname(os.path.abspath(__file__)), "realm", "static")
    )
    
    # Configure app
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-key-for-realm-app")
    app.config["MSEO_SERVER_URL"] = mseo_server_url
    
    # Set up MCP client
    mcp_client = MCPClient(mseo_server_url)
    
    # Configure MSEO service
    mseo_service.set_mcp_client(mcp_client)
    
    # Register routes
    register_routes(app)
    
    # Create a health check route
    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})
    
    return app

def main():
    """Main entry point."""
    args = parse_args()
    
    # Set log level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Debug mode enabled")
    
    # Check if MSEO server is running
    mseo_server_process = None
    if not is_mseo_server_running(args.mseo_server) and args.auto_start_mseo:
        mseo_server_process = start_mseo_server()
    
    try:
        # Create app
        app = create_app(args.mseo_server)
        
        # Run app
        logger.info(f"Starting REALM app on {args.host}:{args.port}")
        app.run(host=args.host, port=args.port, debug=args.debug)
        
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Error running REALM app: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 1
    finally:
        # Clean up MSEO server process if we started it
        if mseo_server_process:
            logger.info("Stopping MSEO MCP server...")
            mseo_server_process.terminate()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
