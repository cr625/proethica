#!/usr/bin/env python3
"""
ProEthica and Unified Ontology Server Verification Script

This script verifies that:
1. The ProEthica Flask application can start
2. The unified ontology server is running and accessible
3. The two can communicate properly

Usage:
    python verify_proethica_ontology.py
"""

import os
import sys
import json
import time
import requests
import subprocess
import signal
from urllib.parse import urljoin
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ProEthica-Verification')

# Load environment variables
load_dotenv()

# Configuration
FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))
ONTOLOGY_SERVER_PORT = int(os.getenv('MCP_SERVER_PORT', '5001'))
FLASK_URL = f"http://localhost:{FLASK_PORT}"
ONTOLOGY_SERVER_URL = f"http://localhost:{ONTOLOGY_SERVER_PORT}"
FLASK_PROCESS = None
ONTOLOGY_SERVER_PROCESS = None
TIMEOUT = 10  # seconds

def check_server_running(url, endpoint="/", timeout=5):
    """Check if a server is running at the given URL"""
    try:
        response = requests.get(urljoin(url, endpoint), timeout=timeout)
        return response.status_code == 200
    except requests.RequestException:
        return False

def start_unified_ontology_server():
    """Start the unified ontology server"""
    global ONTOLOGY_SERVER_PROCESS
    logger.info("Starting unified ontology server...")
    
    # Check if the server is already running
    if check_server_running(ONTOLOGY_SERVER_URL, "/info"):
        logger.info("Unified ontology server is already running")
        return True
        
    try:
        # Start the server
        server_script = os.path.join(os.getcwd(), "run_unified_mcp_server.py")
        if not os.path.isfile(server_script):
            logger.error(f"Server script not found: {server_script}")
            return False
            
        ONTOLOGY_SERVER_PROCESS = subprocess.Popen(
            [sys.executable, server_script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for the server to start
        start_time = time.time()
        while time.time() - start_time < TIMEOUT:
            if check_server_running(ONTOLOGY_SERVER_URL, "/info"):
                logger.info("Unified ontology server started successfully")
                return True
            time.sleep(0.5)
            
        logger.error("Failed to start unified ontology server (timeout)")
        return False
    except Exception as e:
        logger.error(f"Error starting unified ontology server: {e}")
        return False

def start_flask_app():
    """Start the Flask application"""
    global FLASK_PROCESS
    logger.info("Starting ProEthica Flask application...")
    
    # Check if the app is already running
    if check_server_running(FLASK_URL):
        logger.info("ProEthica Flask application is already running")
        return True
        
    try:
        # Start the Flask app
        flask_script = os.path.join(os.getcwd(), "run.py")
        if not os.path.isfile(flask_script):
            logger.error(f"Flask script not found: {flask_script}")
            return False
            
        env = os.environ.copy()
        env["FLASK_ENV"] = "development"
        
        # Set database port for Docker PostgreSQL
        if 'DB_PORT' not in env:
            env["DB_PORT"] = "5433"  # Docker PostgreSQL runs on port 5433
        
        FLASK_PROCESS = subprocess.Popen(
            [sys.executable, flask_script],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        
        # Wait for the app to start
        start_time = time.time()
        while time.time() - start_time < TIMEOUT:
            if check_server_running(FLASK_URL):
                logger.info("ProEthica Flask application started successfully")
                return True
            time.sleep(0.5)
            
        logger.error("Failed to start ProEthica Flask application (timeout)")
        return False
    except Exception as e:
        logger.error(f"Error starting ProEthica Flask application: {e}")
        return False

def check_ontology_connection():
    """Check if the Flask app can connect to the ontology server"""
    logger.info("Testing connection between Flask app and ontology server...")
    
    try:
        # First, check if we can directly access the ontology server
        response = requests.get(f"{ONTOLOGY_SERVER_URL}/info")
        if response.status_code != 200:
            logger.error("Unable to access ontology server directly")
            return False
        
        # Then check if we can access the ontology through the Flask app
        # This endpoint should be implemented to test the connection
        response = requests.get(f"{FLASK_URL}/api/ontology/status")
        
        # If the endpoint doesn't exist, we'll suggest creating it
        if response.status_code == 404:
            logger.warning("Connection test endpoint not found. Need to implement /api/ontology/status endpoint.")
            return None
            
        if response.status_code != 200:
            logger.error(f"Connection test failed with status code: {response.status_code}")
            return False
            
        logger.info("Connection test successful")
        return True
    except requests.RequestException as e:
        logger.error(f"Error testing connection: {e}")
        return False

def cleanup():
    """Clean up processes on exit"""
    logger.info("Cleaning up processes...")
    
    if FLASK_PROCESS:
        FLASK_PROCESS.terminate()
        try:
            FLASK_PROCESS.wait(timeout=5)
        except subprocess.TimeoutExpired:
            FLASK_PROCESS.kill()
            
    if ONTOLOGY_SERVER_PROCESS:
        ONTOLOGY_SERVER_PROCESS.terminate()
        try:
            ONTOLOGY_SERVER_PROCESS.wait(timeout=5)
        except subprocess.TimeoutExpired:
            ONTOLOGY_SERVER_PROCESS.kill()

def create_test_endpoint_example():
    """Print example code for creating a test endpoint"""
    logger.info("To verify the connection, add this endpoint to your Flask app:")
    
    example_code = '''
# Add to your routes/__init__.py or create a new file routes/ontology_routes.py

from flask import Blueprint, jsonify
import requests
import os

bp = Blueprint('ontology', __name__, url_prefix='/api/ontology')

@bp.route('/status', methods=['GET'])
def ontology_status():
    """Test the connection to the ontology server"""
    ontology_url = os.getenv('MCP_SERVER_URL', 'http://localhost:5001')
    
    try:
        # Try to get info from the ontology server
        response = requests.get(f"{ontology_url}/info", timeout=5)
        
        if response.status_code == 200:
            # Get server info
            info = response.json()
            
            return jsonify({
                'status': 'connected',
                'ontology_server': ontology_url,
                'server_info': info,
                'message': 'Successfully connected to the ontology server'
            })
        else:
            return jsonify({
                'status': 'error',
                'message': f"Failed to connect to ontology server: HTTP {response.status_code}"
            }), 500
            
    except requests.RequestException as e:
        return jsonify({
            'status': 'error',
            'message': f"Failed to connect to ontology server: {str(e)}"
        }), 500

# Then register the blueprint in your app/__init__.py:
# from app.routes import ontology_routes
# app.register_blueprint(ontology_routes.bp)
'''
    print(example_code)

def main():
    """Main verification function"""
    try:
        logger.info("Starting verification...")
        
        # Step 1: Start the ontology server
        if not start_unified_ontology_server():
            logger.error("Failed to start or connect to the unified ontology server")
            return False
            
        # Step 2: Start the Flask app
        if not start_flask_app():
            logger.error("Failed to start the ProEthica Flask application")
            return False
            
        # Step 3: Check the connection
        connection_result = check_ontology_connection()
        
        # If the endpoint doesn't exist, suggest creating it
        if connection_result is None:
            create_test_endpoint_example()
            logger.info("Verification incomplete: connection test endpoint needs to be implemented")
            return None
            
        if not connection_result:
            logger.error("Connection test failed")
            return False
            
        logger.info("Verification completed successfully")
        return True
    
    except Exception as e:
        logger.error(f"Verification failed with error: {e}")
        return False
    finally:
        cleanup()

if __name__ == "__main__":
    result = main()
    if result is True:
        print("\n✓ Verification completed successfully")
        sys.exit(0)
    elif result is None:
        print("\n⚠ Verification incomplete, follow the instructions above")
        sys.exit(1)
    else:
        print("\n✗ Verification failed")
        sys.exit(2)
