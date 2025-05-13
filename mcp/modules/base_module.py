#!/usr/bin/env python3
"""
Base Module for Unified Ontology Server

This module provides a base class for creating modules that can be loaded
into the unified ontology server.
"""

import logging
from typing import Dict, Any, Callable

class BaseModule:
    """
    Base class for server modules.
    
    This class provides the basic structure and functionality for MCP server modules,
    including tool registration, handling of tool calls, and utility functions.
    """
    
    def __init__(self, server=None):
        """
        Initialize the module.
        
        Args:
            server: The MCP server instance that will host this module
        """
        self.server = server
        self.tools = {}
        self._register_tools()
        
    def _register_tools(self) -> None:
        """
        Register the tools provided by this module.
        
        This method should be overridden by derived classes to register their tools.
        """
        self.tools = {}
    
    @property
    def name(self) -> str:
        """
        Get the name of this module.
        
        Returns:
            String name of the module
        """
        return "base_module"
    
    @property
    def description(self) -> str:
        """
        Get the description of this module.
        
        Returns:
            String description of the module
        """
        return "Base module for MCP server extensions"
    
    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a call to a tool in this module.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            
        Returns:
            Result of the tool execution
            
        Raises:
            ValueError: If the tool is not found
        """
        if tool_name not in self.tools:
            raise ValueError(f"Tool '{tool_name}' not found in module '{self.name}'")
        
        # Get the tool handler
        handler = self.tools[tool_name]
        
        # Call the tool handler
        try:
            # Check if the handler is a coroutine function
            if hasattr(handler, '__await__'):
                # If it's awaitable, await it
                result = await handler(arguments)
            else:
                # Otherwise call it directly
                result = handler(arguments)
                
            # Format the result for JSON-RPC response
            if isinstance(result, dict) and "content" in result:
                return result
            else:
                # Wrap the result in the expected format
                return {"content": [{"text": result}]}
        except Exception as e:
            # Log the error
            logging.error(f"Error executing tool {tool_name}: {str(e)}")
            import traceback
            traceback.print_exc()
            
            # Return an error response
            return {"content": [{"text": {"error": f"Error executing tool {tool_name}: {str(e)}"}}]}
