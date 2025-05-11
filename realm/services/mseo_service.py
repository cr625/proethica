"""
MSEO Service.

This module provides a service for interacting with the MSEO MCP server.
"""

import os
import logging
import requests
from typing import Dict, List, Any, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MSEOService:
    """Service for interacting with the MSEO MCP server."""
    
    def __init__(self, mcp_client=None, server_name="mseo-mcp-server"):
        """Initialize the service.
        
        Args:
            mcp_client: MCP client instance
            server_name: Name of the MSEO MCP server
        """
        self.mcp_client = mcp_client
        self.server_name = server_name
    
    def set_mcp_client(self, mcp_client):
        """Set the MCP client.
        
        Args:
            mcp_client: MCP client instance
        """
        self.mcp_client = mcp_client
    
    def _use_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Use an MCP tool.
        
        Args:
            tool_name: Name of the tool to use
            arguments: Arguments for the tool
            
        Returns:
            Tool response
        """
        if not self.mcp_client:
            logger.error("MCP client not set")
            return {"error": "MCP client not set"}
        
        try:
            result = self.mcp_client.use_tool(
                server_name=self.server_name,
                tool_name=tool_name,
                arguments=arguments
            )
            return result
        except Exception as e:
            logger.error(f"Error using MCP tool {tool_name}: {e}")
            return {"error": str(e)}
    
    def search_materials(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for materials.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            List of materials
        """
        result = self._use_tool("search_ontology", {
            "query": query,
            "type": "material",
            "limit": limit
        })
        
        if "error" in result:
            logger.error(f"Error searching materials: {result['error']}")
            return []
        
        return result.get("materials", [])
    
    def get_material_details(self, uri: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific material.
        
        Args:
            uri: URI of the material
            
        Returns:
            Material details, or None if not found
        """
        result = self._use_tool("get_material", {
            "uri": uri
        })
        
        if "error" in result:
            logger.error(f"Error getting material details: {result['error']}")
            return None
        
        return result
    
    def get_material_properties(self, uri: str) -> List[Dict[str, Any]]:
        """Get properties for a specific material.
        
        Args:
            uri: URI of the material
            
        Returns:
            List of properties
        """
        result = self._use_tool("get_material_properties", {
            "uri": uri
        })
        
        if "error" in result:
            logger.error(f"Error getting material properties: {result['error']}")
            return []
        
        return result.get("properties", [])
    
    def get_categories(self) -> List[Dict[str, Any]]:
        """Get a list of material categories.
        
        Returns:
            List of categories
        """
        result = self._use_tool("get_categories", {})
        
        if "error" in result:
            logger.error(f"Error getting categories: {result['error']}")
            return []
        
        return result.get("categories", [])
    
    def get_category_details(self, uri: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific category.
        
        Args:
            uri: URI of the category
            
        Returns:
            Category details, or None if not found
        """
        result = self._use_tool("get_category", {
            "uri": uri
        })
        
        if "error" in result:
            logger.error(f"Error getting category details: {result['error']}")
            return None
        
        return result
    
    def compare_materials(self, uri1: str, uri2: str) -> Dict[str, Any]:
        """Compare two materials.
        
        Args:
            uri1: URI of the first material
            uri2: URI of the second material
            
        Returns:
            Comparison results
        """
        result = self._use_tool("compare_materials", {
            "uri1": uri1,
            "uri2": uri2
        })
        
        if "error" in result:
            logger.error(f"Error comparing materials: {result['error']}")
            return {"error": result["error"]}
        
        return result
    
    def chat_with_context(self, user_message: str, conversation_history: List[Dict[str, str]] = None) -> str:
        """Generate a chat response with MSEO ontology context.
        
        Args:
            user_message: User message
            conversation_history: Previous conversation messages
            
        Returns:
            Assistant response
        """
        # Prepare conversation history
        if conversation_history is None:
            conversation_history = []
        
        # Add current user message
        messages = conversation_history + [{"role": "user", "content": user_message}]
        
        # Use chat completion tool
        result = self._use_tool("chat_completion", {
            "messages": messages,
            "include_ontology_context": True
        })
        
        if "error" in result:
            logger.error(f"Error in chat completion: {result['error']}")
            return f"I'm sorry, I encountered an error: {result['error']}"
        
        return result.get("content", "I apologize, but I couldn't generate a response.")

# Create a singleton instance
mseo_service = MSEOService()
