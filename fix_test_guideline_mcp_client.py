#!/usr/bin/env python3
"""
Script to fix test_guideline_mcp_client.py to properly access the JSON-RPC endpoint
"""
import sys
import os

def fix_client():
    """Fix the MCP client to properly access the JSON-RPC endpoint"""
    
    client_path = "test_guideline_mcp_client.py"
    
    if not os.path.exists(client_path):
        print(f"Error: {client_path} not found")
        return False
    
    try:
        with open(client_path, 'r') as f:
            content = f.read()
        
        # Fix 1: Correct the wait_for_server function to access the jsonrpc endpoint
        content = content.replace(
            """def wait_for_server(timeout=30):
    \"\"\"Wait for the server to start, with timeout.\"\"\"
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
    return False""",
            """def wait_for_server(timeout=30):
    \"\"\"Wait for the server to start, with timeout.\"\"\"
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
    return False"""
        )
        
        # Write the fixed content back
        with open(client_path, 'w') as f:
            f.write(content)
        
        print(f"✅ Fixed {client_path}")
        return True
    
    except Exception as e:
        print(f"Error fixing client: {str(e)}")
        return False

if __name__ == "__main__":
    if fix_client():
        print("Fix applied successfully. Try running the client again")
    else:
        print("Failed to apply fix")
        sys.exit(1)
