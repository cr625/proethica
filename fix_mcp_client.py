#!/usr/bin/env python3
"""
Fix MCP Client

This script updates the app/services/mcp_client.py file to use the JSON-RPC endpoint
instead of deprecated API endpoints for connectivity checks and updates the Claude model
reference to use the latest version.
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

def fix_mcp_client() -> bool:
    """Fix the MCP client to use JSON-RPC and update model references."""
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
    
    # Fix 1: Replace the old API endpoint checks with JSON-RPC endpoint check
    # Find the section where the server is checked
    connection_check_pattern = r'def is_server_available\([^)]*\):.*?return False'
    connection_check_match = re.search(connection_check_pattern, content, re.DOTALL)
    
    if connection_check_match:
        old_check = connection_check_match.group(0)
        
        # Create the new check using JSON-RPC
        new_check = '''def is_server_available(self, timeout=5):
        """Check if the MCP server is available using JSON-RPC endpoint."""
        logger.info(f"Testing connection to MCP server at {self.mcp_server_url}...")
        
        try:
            # Try JSON-RPC endpoint with list_tools method
            jsonrpc_url = f"{self.mcp_server_url}/jsonrpc"
            response = requests.post(
                jsonrpc_url,
                json={
                    "jsonrpc": "2.0",
                    "method": "list_tools",
                    "params": {},
                    "id": 1
                },
                timeout=timeout
            )
            
            if response.status_code == 200:
                logger.info("Successfully connected to MCP server JSON-RPC endpoint")
                return True
                
            logger.warning(f"JSON-RPC endpoint returned status code {response.status_code}")
            
            # If JSON-RPC fails, try older ping endpoint as fallback
            ping_url = f"{self.mcp_server_url}/api/ping"
            response = requests.get(ping_url, timeout=timeout)
            
            if response.status_code == 200:
                logger.info("Successfully connected to MCP server ping endpoint")
                return True
                
            logger.warning(f"MCP server ping endpoint returned status code {response.status_code}")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error connecting to MCP server: {e}")
        
        logger.error("All connection attempts to MCP server failed")
        return False'''
        
        # Replace the old check with the new one
        content = content.replace(old_check, new_check)
    else:
        logger.warning("Could not find the is_server_available method in the MCP client")
    
    # Fix 2: Update Claude model references
    content = re.sub(
        r'claude-3-opus-20240229',
        'claude-3-7-sonnet-20250219',
        content
    )
    
    content = re.sub(
        r'claude-3-sonnet-20240229',
        'claude-3-7-sonnet-20250219',
        content
    )
    
    content = re.sub(
        r'claude-3-opus-[0-9]+',
        'claude-3-7-sonnet-20250219',
        content
    )
    
    content = re.sub(
        r'claude-3-sonnet-[0-9]+',
        'claude-3-7-sonnet-20250219',
        content
    )
    
    # Fix 3: Update the testing endpoints array to use JSON-RPC
    endpoints_pattern = r'endpoints\s*=\s*\[\s*.*?\s*\]'
    endpoints_match = re.search(endpoints_pattern, content, re.DOTALL)
    
    if endpoints_match:
        old_endpoints = endpoints_match.group(0)
        new_endpoints = '''endpoints = [
            # Check JSON-RPC endpoint
            "/jsonrpc"
        ]'''
        
        content = content.replace(old_endpoints, new_endpoints)
    else:
        logger.warning("Could not find the endpoints array in the MCP client")
    
    # Write the updated content back to the file
    if write_file(MCP_CLIENT_PATH, content):
        logger.info(f"Successfully updated MCP client at {MCP_CLIENT_PATH}")
        return True
    else:
        # Restore from backup if the write failed
        logger.warning(f"Failed to update MCP client, restoring from backup {backup_path}")
        restore_content = read_file(backup_path)
        if restore_content and write_file(MCP_CLIENT_PATH, restore_content):
            logger.info(f"Restored from backup {backup_path}")
        else:
            logger.error(f"Failed to restore from backup {backup_path}")
        return False

def main() -> int:
    """Main function."""
    logger.info("Starting MCP Client Fix")
    
    if fix_mcp_client():
        logger.info("MCP Client fix completed successfully")
        return 0
    else:
        logger.error("MCP Client fix failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
