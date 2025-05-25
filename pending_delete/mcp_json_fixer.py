#!/usr/bin/env python3
"""
MCP JSON Response Fixer

This script creates a simple proxy that fixes JSON formatting issues
in MCP server responses.
"""

import os
import sys
import json
import logging
from flask import Flask, request, jsonify
import requests

# Set up logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Create Flask application
app = Flask(__name__)

# Target MCP server - default to localhost:5001 but without the /jsonrpc part
TARGET_MCP_SERVER = os.environ.get('TARGET_MCP_SERVER', 'http://localhost:5001')

@app.route('/jsonrpc', methods=['POST'])
def jsonrpc_proxy():
    """Forward JSON-RPC requests and fix responses"""
    # Get the incoming JSON-RPC request
    try:
        request_data = request.get_json()
        logger.info(f"Received request for method: {request_data.get('method', 'unknown')}")
        
        # Forward the request to the target MCP server
        response = requests.post(
            f"{TARGET_MCP_SERVER}/jsonrpc",
            json=request_data,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        
        # Get the raw response text
        raw_response = response.text
        logger.debug(f"Raw response: {raw_response[:200]}...")
        
        # Try to fix common JSON issues
        try:
            # First try to parse as is
            result = json.loads(raw_response)
        except json.JSONDecodeError as e:
            logger.warning(f"JSON decode error, attempting to fix: {e}")
            
            # Fix common issues
            fixed_response = raw_response
            
            # Fix 1: Remove BOM or other invisible characters at the start
            fixed_response = fixed_response.lstrip()
            
            # Fix 2: Remove any trailing commas in arrays or objects
            fixed_response = fixed_response.replace(',]', ']').replace(',}', '}')
            
            # Fix 3: Ensure string values are properly quoted
            # (This is a simplistic approach - a more robust parsing would be needed for complex cases)
            
            # Try to parse the fixed response
            try:
                result = json.loads(fixed_response)
                logger.info("Successfully fixed JSON response!")
            except json.JSONDecodeError as new_e:
                logger.error(f"Could not fix JSON: {new_e}")
                # Return error information
                return jsonify({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": f"Parse error in MCP response: {str(new_e)}"
                    },
                    "id": request_data.get('id')
                }), 500
        
        # Return the fixed JSON response
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error processing request: {e}")
        return jsonify({
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            },
            "id": None
        }), 500

if __name__ == '__main__':
    # Get port from environment or use default
    port = int(os.environ.get('PORT', 5002))
    logger.info(f"Starting MCP JSON fixer proxy on port {port}")
    logger.info(f"Target MCP server: {TARGET_MCP_SERVER}")
    app.run(host='0.0.0.0', port=port, debug=True)
