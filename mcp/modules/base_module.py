#!/usr/bin/env python3
"""
Base Module for MCP Servers

This module provides the base class for MCP server modules.
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)

class MCPBaseModule:
    """
    Base class for MCP server modules.
    
    This class provides the basic structure for a module that can be
    added to an MCP server. It includes methods for registering tools
    and resources.
    """
    
    def __init__(self, name: str):
        """
        Initialize the module.
        
        Args:
            name: The name of the module
        """
        self.name = name
        self.tools = {}
        self.resources = {}
        
        # Register this module's tools and resources
        self._register_tools()
        self._register_resources()
        
        logger.info(f"Initialized {self.name} module")
    
    def _register_tools(self):
        """
        Register this module's tools.
        
        This method should be overridden by subclasses to register their tools.
        """
        pass
    
    def _register_resources(self):
        """
        Register this module's resources.
        
        This method should be overridden by subclasses to register their resources.
        """
        pass
    
    def register_tool(self, name: str, handler, description: str, input_schema: Dict[str, Any]):
        """
        Register a tool with the module.
        
        Args:
            name: The name of the tool
            handler: The function that implements the tool
            description: A description of the tool
            input_schema: The JSON schema for the tool's input
        """
        self.tools[name] = {
            "handler": handler,
            "description": description,
            "input_schema": input_schema
        }
        logger.debug(f"Registered tool '{name}' with {self.name} module")
    
    def register_resource(self, uri: str, handler, description: str):
        """
        Register a resource with the module.
        
        Args:
            uri: The URI of the resource
            handler: The function that implements the resource
            description: A description of the resource
        """
        self.resources[uri] = {
            "handler": handler,
            "description": description
        }
        logger.debug(f"Registered resource '{uri}' with {self.name} module")
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get the list of tools registered with this module.
        
        Returns:
            A list of tool definitions
        """
        return [
            {
                "name": name,
                "description": info["description"],
                "input_schema": info["input_schema"]
            }
            for name, info in self.tools.items()
        ]
    
    def get_resources(self) -> List[Dict[str, Any]]:
        """
        Get the list of resources registered with this module.
        
        Returns:
            A list of resource definitions
        """
        return [
            {
                "uri": uri,
                "description": info["description"]
            }
            for uri, info in self.resources.items()
        ]
    
    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Call a tool registered with this module.
        
        Args:
            name: The name of the tool to call
            arguments: The arguments to pass to the tool
            
        Returns:
            The result of the tool call
            
        Raises:
            ValueError: If the tool is not found
        """
        if name not in self.tools:
            raise ValueError(f"Tool '{name}' not found in {self.name} module")
        
        handler = self.tools[name]["handler"]
        try:
            result = await handler(arguments)
            return result
        except Exception as e:
            logger.error(f"Error calling tool '{name}': {str(e)}")
            raise
    
    async def access_resource(self, uri: str) -> Dict[str, Any]:
        """
        Access a resource registered with this module.
        
        Args:
            uri: The URI of the resource to access
            
        Returns:
            The resource data
            
        Raises:
            ValueError: If the resource is not found
        """
        if uri not in self.resources:
            raise ValueError(f"Resource '{uri}' not found in {self.name} module")
        
        handler = self.resources[uri]["handler"]
        try:
            result = await handler()
            return result
        except Exception as e:
            logger.error(f"Error accessing resource '{uri}': {str(e)}")
            raise
