"""
MCP Client Service.

This module provides a client for interacting with MCP servers.
"""

import os
import logging
import requests
import json
from functools import lru_cache
from flask import current_app

# Configure logging
logger = logging.getLogger(__name__)

class MCPClient:
    """Model Context Protocol client."""
    
    def __init__(self, base_url=None):
        """Initialize the client.
        
        Args:
            base_url: Base URL of the MCP server
        """
        self.base_url = base_url or os.environ.get('MCP_BASE_URL', 'http://localhost:5001')
        logger.info(f"Initialized MCP client with base URL: {self.base_url}")
    
    def use_tool(self, server_name, tool_name, arguments):
        """Use an MCP tool.
        
        Args:
            server_name: Name of the MCP server
            tool_name: Name of the tool to use
            arguments: Tool arguments
            
        Returns:
            Tool response
        """
        url = f"{self.base_url}/mcp/{server_name}/tools/{tool_name}"
        
        try:
            logger.debug(f"Calling MCP tool: {server_name}/{tool_name} with args: {arguments}")
            response = requests.post(url, json=arguments)
            response.raise_for_status()
            
            result = response.json()
            logger.debug(f"MCP tool response: {result}")
            
            return result
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling MCP tool {server_name}/{tool_name}: {e}")
            raise
    
    def access_resource(self, server_name, uri):
        """Access an MCP resource.
        
        Args:
            server_name: Name of the MCP server
            uri: URI of the resource
            
        Returns:
            Resource data
        """
        url = f"{self.base_url}/mcp/{server_name}/resources/{uri}"
        
        try:
            logger.debug(f"Accessing MCP resource: {server_name}/{uri}")
            response = requests.get(url)
            response.raise_for_status()
            
            result = response.json()
            logger.debug(f"MCP resource response: {result}")
            
            return result
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Error accessing MCP resource {server_name}/{uri}: {e}")
            raise

@lru_cache(maxsize=1)
def get_mcp_client():
    """Get a cached MCP client instance.
    
    Returns:
        MCPClient instance
    """
    try:
        base_url = current_app.config.get('MCP_BASE_URL')
    except RuntimeError:
        # Not in a Flask context
        base_url = os.environ.get('MCP_BASE_URL')
    
    return MCPClient(base_url=base_url)
