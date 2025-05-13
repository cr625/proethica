#!/usr/bin/env python3
"""
Fix Test Guideline MCP Client

This script fixes the test_guideline_mcp_client.py file to correctly check
for server availability using the JSON-RPC endpoint instead of the root URL.
"""

import os
import sys
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Path to the test client file
TEST_CLIENT_PATH = "test_guideline_mcp_client.py"

def fix_client_file():
    """Fix the wait_for_server function in the test client file."""
    if not os.path.exists(TEST_CLIENT_PATH):
        logger.error(f"Test client file not found: {TEST_CLIENT_PATH}")
        return False
    
    try:
        # Read the file
        with open(TEST_CLIENT_PATH, "r") as f:
            content = f.read()
        
        # Check if it's already fixed
        if 'jsonrpc' in content and 'list_tools' in content and '"jsonrpc": "2.0"' in content:
            logger.info("Client file is already fixed. No changes needed.")
            return True
        
        # Look for the wait_for_server function
        if "def wait_for_server(" not in content:
            logger.error("Could not find wait_for_server function in test client")
            return False
        
        # Replace the function with the fixed version
        old_function = '''def wait_for_server(timeout=30):
    """Wait for the server to start, with timeout."""
    logger.info(f"Waiting up to {timeout} seconds for MCP server...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(f"{MCP_URL}", timeout=2)
            if response.status_code == 200:
                logger.info("MCP server is running!")
                return True
        except requests.exceptions.RequestException:
            # Keep waiting
            pass
        
        time.sleep(1)
    
    logger.error(f"Timed out after {timeout} seconds waiting for server to start")
    return False'''
        
        new_function = '''def wait_for_server(timeout=30):
    """Wait for the server to start, with timeout."""
    logger.info(f"Waiting up to {timeout} seconds for MCP server...")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            # Test the JSON-RPC endpoint with a simple ping request
            response = requests.post(
                f"{MCP_URL}/jsonrpc",
                json={
                    "jsonrpc": "2.0",
                    "method": "list_tools",
                    "params": {},
                    "id": 0
                },
                timeout=2
            )
            if response.status_code == 200:
                logger.info("MCP server is running!")
                return True
        except requests.exceptions.RequestException:
            # Keep waiting
            pass
        
        time.sleep(1)
    
    logger.error(f"Timed out after {timeout} seconds waiting for server to start")
    return False'''
        
        # Replace the function
        updated_content = content.replace(old_function, new_function)
        
        # If the specific function wasn't found, try a more general approach
        if updated_content == content:
            import re
            pattern = r"def wait_for_server\([^)]*\):[^}]*?response = requests\.get[^}]*?return False"
            match = re.search(pattern, content, re.DOTALL)
            
            if match:
                updated_content = content.replace(match.group(0), new_function)
            else:
                logger.warning("Could not find exact match for wait_for_server function.")
                logger.info("Trying to update the client in a general way...")
                
                # Here we would implement a more sophisticated fix
                # For now, just inject the new function after imports
                imports_end = content.find("logger = logging.getLogger(__name__)") + len("logger = logging.getLogger(__name__)")
                
                updated_content = (
                    content[:imports_end + 1] + 
                    "\n\n# Updated server check function\n" + 
                    new_function + 
                    "\n\n# Original code continues below\n" + 
                    content[imports_end + 1:]
                )
        
        # Write the updated content
        with open(TEST_CLIENT_PATH, "w") as f:
            f.write(updated_content)
        
        logger.info(f"Successfully updated {TEST_CLIENT_PATH} with JSON-RPC endpoint check")
        return True
        
    except Exception as e:
        logger.error(f"Error fixing test client: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Main function."""
    logger.info("Starting Test Guideline MCP Client fix")
    
    if fix_client_file():
        logger.info("Fix completed successfully!")
        return 0
    else:
        logger.error("Fix failed. Please check the logs.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
