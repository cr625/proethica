#!/usr/bin/env python3
"""
Final Fix for MCP Client JSON-RPC

This script fixes the remaining issues with the MCP client JSON-RPC handling
by updating the endpoint check to properly use the POST method for /jsonrpc
instead of GET.
"""

import os
import sys
import re
import logging
from typing import List, Dict, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Path to the MCP client file
MCP_CLIENT_PATH = "app/services/mcp_client.py"

def read_file(file_path: str) -> Optional[str]:
    """Read a file and return its contents as a string."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return None

def write_file(file_path: str, content: str) -> bool:
    """Write content to a file."""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"Error writing to file {file_path}: {e}")
        return False

def backup_file(file_path: str) -> Optional[str]:
    """Create a backup of a file."""
    import datetime
    
    backup_path = f"{file_path}.bak.{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    try:
        content = read_file(file_path)
        if content is None:
            return None
        
        if write_file(backup_path, content):
            logger.info(f"Created backup at {backup_path}")
            return backup_path
        else:
            return None
    except Exception as e:
        logger.error(f"Error creating backup of {file_path}: {e}")
        return None

def fix_jsonrpc_endpoint_method() -> bool:
    """Fix the endpoint testing to use POST for /jsonrpc instead of GET."""
    # Check if the file exists
    if not os.path.exists(MCP_CLIENT_PATH):
        logger.error(f"MCP client file not found: {MCP_CLIENT_PATH}")
        return False
    
    # Create a backup
    backup_path = backup_file(MCP_CLIENT_PATH)
    if backup_path is None:
        logger.error("Failed to create backup, aborting")
        return False
    
    # Read the file
    content = read_file(MCP_CLIENT_PATH)
    if content is None:
        return False
    
    # Find the checking endpoint code
    endpoint_check_pattern = r'Checking endpoint: http://[^/]+/jsonrpc[^}]*?response = requests\.get\('
    endpoint_check_match = re.search(endpoint_check_pattern, content, re.DOTALL)
    
    if endpoint_check_match:
        old_get_code = 'response = requests.get('
        new_post_code = '''response = requests.post(
            jsonrpc_url,
            json={
                "jsonrpc": "2.0",
                "method": "list_tools", 
                "params": {}, 
                "id": 1
            },'''
        
        # Replace the GET with POST and JSON-RPC payload
        updated_content = content.replace(old_get_code, new_post_code)
        
        # Also fix any instances of checking for "/jsonrpc" endpoint with GET
        endpoints_get_pattern = r'"/jsonrpc"[^}]*?response = requests\.get\('
        endpoints_get_match = re.search(endpoints_get_pattern, updated_content, re.DOTALL)
        
        if endpoints_get_match:
            # Find the specific endpoint check context
            endpoint_context = endpoints_get_match.group(0)
            # Replace only the GET call in that context
            updated_endpoint_context = endpoint_context.replace(
                'response = requests.get(',
                'response = requests.post('
            )
            updated_content = updated_content.replace(endpoint_context, updated_endpoint_context)
        
        # Write the updated content
        if write_file(MCP_CLIENT_PATH, updated_content):
            logger.info(f"Successfully fixed JSON-RPC endpoint method in {MCP_CLIENT_PATH}")
            return True
        else:
            return False
    else:
        logger.info("No GET request to /jsonrpc found in the file, checking if already using POST...")
        
        # Check if it's already using POST
        if 'requests.post' in content and '/jsonrpc' in content:
            logger.info("File is already using POST for JSON-RPC, no changes needed")
            return True
        else:
            logger.warning("Could not find specific pattern to fix")
            return False

def main() -> int:
    """Main function."""
    logger.info("Starting final JSON-RPC endpoint method fix")
    
    if fix_jsonrpc_endpoint_method():
        logger.info("JSON-RPC endpoint method fix completed successfully")
        return 0
    else:
        logger.error("JSON-RPC endpoint method fix failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
