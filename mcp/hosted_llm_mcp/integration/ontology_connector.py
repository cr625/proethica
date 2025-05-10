"""
Ontology Connector

This module provides a connector to the existing enhanced ontology MCP server
to retrieve ontology data and perform operations on the ontology.
"""

import os
import json
import logging
import aiohttp
import asyncio
from typing import Dict, Any, List, Optional, Union

logger = logging.getLogger(__name__)

class OntologyConnector:
    """
    Connector to the enhanced ontology MCP server.
    
    This class provides methods to:
    1. Retrieve ontology classes, properties, and instances
    2. Query for specific ontology elements
    3. Submit new ontology elements for validation and potential addition
    4. Get contextual information about ontology structures
    """

    def __init__(self, mcp_url: str = "http://localhost:5001"):
        """
        Initialize the ontology connector.
        
        Args:
            mcp_url: The URL of the enhanced ontology MCP server
        """
        self.mcp_url = mcp_url
        logger.info(f"Initialized ontology connector with MCP URL: {mcp_url}")

    async def _make_request(self, endpoint: str, method: str = "GET", data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Make a request to the enhanced ontology MCP server.
        
        Args:
            endpoint: The API endpoint to call
            method: The HTTP method to use
            data: Optional data for POST requests
            
        Returns:
            The response from the MCP server
        """
        url = f"{self.mcp_url}/{endpoint}"
        
        try:
            async with aiohttp.ClientSession() as session:
                if method.upper() == "GET":
                    async with session.get(url) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            logger.error(f"Error from MCP server: {error_text}")
                            return {"success": False, "error": error_text}
                
                elif method.upper() == "POST":
                    async with session.post(url, json=data) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            error_text = await response.text()
                            logger.error(f"Error from MCP server: {error_text}")
                            return {"success": False, "error": error_text}
                
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                    
        except Exception as e:
            logger.error(f"Error connecting to MCP server: {str(e)}")
            return {"success": False, "error": str(e)}

    async def get_ontology_classes(self) -> Dict[str, Any]:
        """Get all ontology classes."""
        return await self._make_request("ontology/classes")

    async def get_ontology_properties(self) -> Dict[str, Any]:
        """Get all ontology properties."""
        return await self._make_request("ontology/properties")

    async def get_ontology_instances(self, class_uri: Optional[str] = None) -> Dict[str, Any]:
        """
        Get ontology instances, optionally filtered by class.
        
        Args:
            class_uri: Optional URI of the class to filter instances
        """
        endpoint = "ontology/instances"
        if class_uri:
            endpoint += f"?class={class_uri}"
        return await self._make_request(endpoint)

    async def get_class_hierarchy(self, root_class: Optional[str] = None) -> Dict[str, Any]:
        """
        Get the class hierarchy, optionally starting from a specific class.
        
        Args:
            root_class: Optional URI of the root class to start the hierarchy from
        """
        endpoint = "ontology/hierarchy"
        if root_class:
            endpoint += f"?root={root_class}"
        return await self._make_request(endpoint)

    async def search_ontology(self, query: str) -> Dict[str, Any]:
        """
        Search the ontology for entities matching the query.
        
        Args:
            query: The search query
        """
        return await self._make_request(f"ontology/search?q={query}")

    async def get_entity_by_uri(self, uri: str) -> Dict[str, Any]:
        """
        Get detailed information about an ontology entity.
        
        Args:
            uri: The URI of the entity
        """
        return await self._make_request(f"ontology/entity?uri={uri}")

    async def get_relationships(self, uri: str) -> Dict[str, Any]:
        """
        Get all relationships for an entity.
        
        Args:
            uri: The URI of the entity
        """
        return await self._make_request(f"ontology/relationships?uri={uri}")

    async def validate_triple(self, subject: str, predicate: str, object: str) -> Dict[str, Any]:
        """
        Validate a potential triple against the ontology.
        
        Args:
            subject: The subject URI or label
            predicate: The predicate URI or label
            object: The object URI or label
        """
        data = {
            "subject": subject,
            "predicate": predicate,
            "object": object
        }
        return await self._make_request("ontology/validate", method="POST", data=data)

    async def suggest_completion(self, partial_triple: Dict[str, Any]) -> Dict[str, Any]:
        """
        Suggest completions for a partial triple.
        
        Args:
            partial_triple: A dictionary with some combination of subject, predicate, object
        """
        return await self._make_request("ontology/suggest", method="POST", data=partial_triple)
        
    async def get_domain_context(self, domain: str) -> Dict[str, Any]:
        """
        Get contextual information about a specific domain in the ontology.
        
        Args:
            domain: The domain name or URI
        """
        return await self._make_request(f"ontology/domain?name={domain}")
