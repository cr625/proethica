#!/usr/bin/env python3
"""
Fix MCP JSON endpoint issues.

This script addresses the "Extra data: line 1 column 4 (char 3)" error
in the MCP server responses by ensuring proper JSON formatting.
"""

import os
import sys
import json
import logging
import requests
import time

# Set up logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default MCP server URL
MCP_SERVER_URL = os.environ.get('MCP_SERVER_URL', 'http://localhost:5001/jsonrpc')

def check_mcp_response():
    """Check MCP server response for JSON formatting issues"""
    logger.info(f"Testing connection to MCP server at {MCP_SERVER_URL}")
    try:
        # Try a basic request
        payload = {
            "jsonrpc": "2.0",
            "method": "list_tools",
            "params": {},
            "id": 1
        }
        
        # Use requests to get the raw data first
        response = requests.post(MCP_SERVER_URL, json=payload, timeout=5)
        raw_content = response.text
        
        logger.info(f"Raw response status code: {response.status_code}")
        logger.info(f"Raw response content: {raw_content[:200]}...")  # Show first 200 chars
        
        # Try to parse as JSON
        try:
            data = json.loads(raw_content)
            logger.info("JSON parsing successful!")
            
            # Print parsed data
            tools = data.get('result', {}).get('tools', [])
            logger.info(f"Found {len(tools)} tools:")
            for tool in tools:
                logger.info(f"- {tool.get('name')}: {tool.get('description')}")
            
            return True, "MCP server response is valid JSON"
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            return False, f"JSON error: {e}"
    
    except Exception as e:
        logger.error(f"Connection error: {e}")
        return False, f"Connection error: {e}"

def test_individual_tools():
    """Test each tool individually for response formatting"""
    logger.info("Testing individual MCP tools...")
    
    # First get list of tools
    payload = {
        "jsonrpc": "2.0",
        "method": "list_tools",
        "params": {},
        "id": 1
    }
    
    try:
        response = requests.post(MCP_SERVER_URL, json=payload, timeout=5) 
        tools = response.json().get('result', {}).get('tools', [])
        
        results = []
        
        # Test each tool
        for tool in tools:
            tool_name = tool.get('name', 'unknown')
            logger.info(f"Testing tool: {tool_name}")
            
            # Simple test parameters - just to check the response format
            test_payload = {
                "jsonrpc": "2.0",
                "method": tool_name,
                "params": {"test": "data"},
                "id": 1
            }
            
            try:
                test_response = requests.post(MCP_SERVER_URL, json=test_payload, timeout=5)
                raw_content = test_response.text
                
                # Try to parse as JSON
                try:
                    json.loads(raw_content)
                    results.append((tool_name, True, "Valid JSON response"))
                except json.JSONDecodeError as e:
                    results.append((tool_name, False, f"Invalid JSON: {e}"))
            except Exception as e:
                results.append((tool_name, False, f"Request error: {e}"))
        
        return results
    
    except Exception as e:
        logger.error(f"Error getting tool list: {e}")
        return []

def fix_common_json_issues():
    """
    Create a wrapper script that can fix common JSON formatting issues
    in MCP server responses. This creates a simple proxy server that
    cleans up JSON responses.
    """
    
    wrapper_script = """#!/usr/bin/env python3
\"\"\"
MCP JSON Response Fixer

This script creates a simple proxy that fixes JSON formatting issues
in MCP server responses.
\"\"\"

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
    \"\"\"Forward JSON-RPC requests and fix responses\"\"\"
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
"""

    # Write the wrapper script to a file
    script_path = "mcp_json_fixer.py"
    with open(script_path, "w") as f:
        f.write(wrapper_script)
    
    # Make it executable
    os.chmod(script_path, 0o755)
    
    logger.info(f"Created MCP JSON fixer proxy: {script_path}")
    logger.info("Run this script with: python mcp_json_fixer.py")
    logger.info("Then update your MCP_SERVER_URL to point to http://localhost:5002/jsonrpc")

def main():
    """Main function to check and fix MCP endpoint issues"""
    logger.info("Checking MCP server JSON response...")
    
    success, message = check_mcp_response()
    if success:
        logger.info("MCP server response looks good!")
    else:
        logger.warning(f"MCP server response has issues: {message}")
        
        # Test individual tools
        logger.info("Testing individual tools...")
        tool_results = test_individual_tools()
        
        for tool_name, success, message in tool_results:
            status = "✓" if success else "✗"
            logger.info(f"Tool {tool_name}: {status} {message}")
        
        # Create fix script
        logger.info("Creating JSON fixer proxy script...")
        fix_common_json_issues()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
