#!/usr/bin/env python3
"""
Base Module for Unified Ontology Server

This module defines the BaseModule abstract class that all modules must inherit from,
providing a consistent interface and common functionality.
"""

import abc
import logging
from typing import Dict, Any, List, Optional, Union, Callable
import json
import asyncio

# Set up logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class BaseModule(abc.ABC):
    """
    Abstract base class for all unified ontology server modules.
    
    Each module provides specific functionality to the unified ontology server,
    such as query capabilities, relationship navigation, temporal features, etc.
    
    Modules must implement the required abstract methods and can optionally
    override other methods to customize behavior.
    """
    
    def __init__(self, server=None):
        """
        Initialize the module.
        
        Args:
            server: The parent server instance this module belongs to
        """
        self.server = server
        self.logger = logging.getLogger(f"{self.__class__.__name__}")
        self.logger.info(f"Initializing {self.__class__.__name__}")
        self.tools = {}  # Will be populated with callable tool handlers
        self._register_tools()
    
    @property
    @abc.abstractmethod
    def name(self) -> str:
        """
        Get the name of the module.
        
        Returns:
            String name identifier for this module
        """
        pass
    
    @property
    @abc.abstractmethod
    def description(self) -> str:
        """
        Get the description of the module.
        
        Returns:
            String description of what this module does
        """
        pass
    
    @abc.abstractmethod
    def _register_tools(self) -> None:
        """
        Register the tools provided by this module.
        
        This method should populate the self.tools dictionary with
        tool_name: handler_method pairs.
        """
        pass
    
    def get_tools(self) -> List[Dict[str, Any]]:
        """
        Get the list of tools provided by this module.
        
        Returns:
            List of tool definitions (name, description, parameters)
        """
        tools = []
        
        for tool_name in self.tools:
            handler = self.tools[tool_name]
            
            # Extract tool metadata from handler docstring
            doc = handler.__doc__ or ""
            description = doc.strip().split("\n")[0] if doc else f"{tool_name} tool"
            
            # Add tool to list
            tools.append({
                "name": tool_name,
                "description": description,
                "module": self.name
            })
            
        return tools
    
    async def handle_tool_call(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle a call to a tool provided by this module.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool execution result
            
        Raises:
            ValueError: If the tool is not found
        """
        if tool_name not in self.tools:
            error_msg = f"Tool '{tool_name}' not found in module '{self.name}'"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
            
        tool_handler = self.tools[tool_name]
        self.logger.info(f"Calling tool '{tool_name}' with arguments: {arguments}")
        
        try:
            # Check if handler is coroutine function
            if asyncio.iscoroutinefunction(tool_handler):
                result = await tool_handler(arguments)
            else:
                result = tool_handler(arguments)
                
            return self._format_result(result)
        except Exception as e:
            self.logger.error(f"Error executing tool '{tool_name}': {str(e)}", exc_info=True)
            return {"error": f"Error executing tool: {str(e)}"}
    
    def _format_result(self, result: Any) -> Dict[str, Any]:
        """
        Format the result from a tool handler for the MCP response.
        
        Args:
            result: Raw result from tool handler
            
        Returns:
            Formatted result for MCP response
        """
        # If result is already a dict with the expected format, return it
        if isinstance(result, dict) and "content" in result:
            return result
            
        # If result is a dict but missing the content wrapper, wrap it
        if isinstance(result, dict):
            try:
                # Try to JSON stringify the dict
                json_str = json.dumps(result)
                return {"content": [{"text": json_str}]}
            except:
                # If that fails, format as string
                return {"content": [{"text": str(result)}]}
                
        # For non-dict results, convert to string
        return {"content": [{"text": str(result)}]}
    
    def initialize(self) -> None:
        """
        Perform any initialization required by this module.
        
        This method is called after the server has been fully initialized
        and can be overridden by modules that need additional setup.
        """
        pass
    
    def shutdown(self) -> None:
        """
        Perform any cleanup required by this module.
        
        This method is called before the server shuts down
        and can be overridden by modules that need cleanup.
        """
        self.logger.info(f"Shutting down {self.__class__.__name__}")
