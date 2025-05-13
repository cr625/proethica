#!/usr/bin/env python3
"""
Test MCP JSON-RPC Connection

This script tests connectivity to the MCP server using the JSON-RPC endpoint.
It provides a cleaner, more reliable way to check if the server is operational.
"""

import sys
import json
import logging
import requests
import argparse
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Default MCP server URL
DEFAULT_MCP_URL = "http://localhost:5001"

def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Test MCP server JSON-RPC connection")
    parser.add_argument(
        "--url", 
        default=DEFAULT_MCP_URL,
        help=f"MCP server URL (default: {DEFAULT_MCP_URL})"
    )
    parser.add_argument(
        "--timeout", 
        type=float, 
        default=10.0,
        help="Connection timeout in seconds (default: 10.0)"
    )
    parser.add_argument(
        "--verbose", 
        "-v", 
        action="store_true",
        help="Display verbose output"
    )
    return parser.parse_args()

def make_jsonrpc_request(
    url: str, 
    method: str, 
    params: Dict[str, Any] = None, 
    timeout: float = 10.0
) -> Optional[Dict[str, Any]]:
    """
    Make a JSON-RPC request to the MCP server.
    
    Args:
        url: The URL of the JSON-RPC endpoint
        method: The JSON-RPC method to call
        params: Parameters to pass to the method (optional)
        timeout: Connection timeout in seconds
        
    Returns:
        The JSON-RPC response result or None if the request failed
    """
    if params is None:
        params = {}
        
    # Prepare the JSON-RPC request
    jsonrpc_request = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": 1
    }
    
    try:
        response = requests.post(
            url,
            json=jsonrpc_request,
            timeout=timeout
        )
        
        # Check if the request was successful
        if response.status_code != 200:
            logger.error(f"Error: Server returned status code {response.status_code}")
            logger.debug(f"Response content: {response.text}")
            return None
            
        # Parse the JSON response
        result = response.json()
        
        # Check for JSON-RPC errors
        if "error" in result:
            logger.error(f"JSON-RPC error: {result['error']}")
            return None
            
        return result
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Connection error: {str(e)}")
        return None
    except json.JSONDecodeError:
        logger.error("Failed to decode JSON response")
        logger.debug(f"Response content: {response.text}")
        return None

def test_server_connection(url: str, timeout: float = 10.0, verbose: bool = False) -> bool:
    """
    Test connection to the MCP server.
    
    Args:
        url: The MCP server URL
        timeout: Connection timeout in seconds
        verbose: Whether to display verbose output
        
    Returns:
        True if the connection was successful, False otherwise
    """
    jsonrpc_url = f"{url}/jsonrpc"
    
    logger.info(f"Testing connection to MCP server at {jsonrpc_url}")
    
    # Try to list the available tools
    result = make_jsonrpc_request(jsonrpc_url, "list_tools", timeout=timeout)
    
    if not result:
        logger.error("Failed to connect to MCP server")
        return False
        
    if "result" not in result:
        logger.error("Invalid response from MCP server (missing 'result' field)")
        return False
    
    tools = result["result"]
    
    if not tools:
        logger.warning("Server returned an empty list of tools")
    else:
        logger.info(f"Server returned {len(tools)} available tools")
        
        if verbose:
            logger.info("Available tools:")
            for tool in tools:
                logger.info(f"  - {tool}")
            
    return True

def main() -> int:
    """Main function."""
    args = parse_args()
    
    # Set log level based on verbose flag
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    
    # Test connection to the server
    success = test_server_connection(
        url=args.url,
        timeout=args.timeout,
        verbose=args.verbose
    )
    
    if success:
        logger.info("✅ MCP server connection successful")
        return 0
    else:
        logger.error("❌ MCP server connection failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
