#!/usr/bin/env python3
"""
Enhanced MCP Client for ontology interactions.

This module provides a wrapper around the basic MCP client that adds simplified
methods for using the enhanced ontology capabilities.
"""

import json
import os
from typing import Dict, List, Any, Optional, Union
import requests

from app.services.mcp_client import MCPClient


class EnhancedMCPClient:
    """
    Enhanced MCP client for interacting with ontologies.
    
    This client provides high-level methods for using the enhanced ontology
    capabilities exposed by the Enhanced Ontology MCP Server.
    """
    
    def __init__(self, base_client=None):
        """
        Initialize the enhanced MCP client.
        
        Args:
            base_client: Optional base MCPClient instance. If not provided,
                a new instance will be created.
        """
        self.base_client = base_client or MCPClient.get_instance()
        self.mcp_url = self.base_client.mcp_url
        self.use_mock_fallback = self.base_client.use_mock_fallback
        self.session = self.base_client.session
        
        print(f"EnhancedMCPClient initialized with MCP_SERVER_URL: {self.mcp_url}")
    
    @classmethod
    def get_instance(cls) -> 'EnhancedMCPClient':
        """Get singleton instance of EnhancedMCPClient."""
        if not hasattr(cls, '_instance') or cls._instance is None:
            base_client = MCPClient.get_instance()
            cls._instance = EnhancedMCPClient(base_client)
        return cls._instance
    
    def check_connection(self) -> bool:
        """Check connection to the enhanced MCP server."""
        return self.base_client.check_connection()
    
    def get_world_entities(self, ontology_source: str, entity_type: str = "all") -> Dict[str, Any]:
        """
        Get entities from the specified ontology.
        
        Args:
            ontology_source: Source of the ontology
            entity_type: Type of entity to retrieve (roles, conditions, resources, etc.)
            
        Returns:
            Dictionary containing entities
        """
        return self.base_client.get_world_entities(ontology_source, entity_type)
    
    def query_ontology(self, ontology_source: str, query: str) -> Dict[str, Any]:
        """
        Execute a SPARQL query against the specified ontology.
        
        Args:
            ontology_source: Source of the ontology
            query: SPARQL query string
            
        Returns:
            Query results
        """
        try:
            print(f"Executing SPARQL query against ontology: {ontology_source}")
            
            # If server is not connected but fallback is enabled, return mock data
            if not self.base_client.is_connected and self.use_mock_fallback:
                print("MCP server not connected, using mock data for query_ontology")
                return {
                    "results": [],
                    "query": query,
                    "is_mock": True,
                    "error": "MCP server not connected (mock fallback)"
                }
            
            # Build JSON-RPC request
            jsonrpc_request = {
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "query_ontology",
                    "arguments": {
                        "ontology_source": ontology_source,
                        "query": query
                    }
                },
                "id": 1
            }
            
            # Send request to MCP server
            response = self.session.post(
                f"{self.mcp_url}/jsonrpc",
                json=jsonrpc_request,
                timeout=30  # Longer timeout for potentially complex queries
            )
            
            # Check response
            if response.status_code == 200:
                result = response.json()
                
                # Check for errors in the JSON-RPC response
                if "error" in result:
                    print(f"Error in JSON-RPC response: {result['error']}")
                    return {
                        "error": result["error"]["message"],
                        "results": [],
                        "query": query
                    }
                
                # Parse the tool result (which is a JSON string in content[0].text)
                if "result" in result and "content" in result["result"]:
                    content_text = result["result"]["content"][0]["text"]
                    return json.loads(content_text)
                else:
                    print(f"Unexpected response format: {result}")
                    return {
                        "error": "Unexpected response format",
                        "results": [],
                        "query": query
                    }
            else:
                error_message = f"Error calling query_ontology: {response.status_code} - {response.text}"
                print(error_message)
                return {
                    "error": error_message,
                    "results": [],
                    "query": query
                }
        except Exception as e:
            error_message = f"Error in query_ontology: {str(e)}"
            print(error_message)
            return {
                "error": error_message,
                "results": [],
                "query": query
            }
    
    def get_entity_relationships(self, ontology_source: str, entity_uri: str, 
                               relationship_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Get relationships for a specific entity.
        
        Args:
            ontology_source: Source of the ontology
            entity_uri: URI of the entity to find relationships for
            relationship_type: Optional type of relationship to filter by
            
        Returns:
            Dictionary with incoming and outgoing relationships
        """
        try:
            print(f"Getting relationships for entity {entity_uri} in ontology {ontology_source}")
            
            # If server is not connected but fallback is enabled, return mock data
            if not self.base_client.is_connected and self.use_mock_fallback:
                print("MCP server not connected, using mock data for get_entity_relationships")
                return {
                    "entity": {"uri": entity_uri, "label": entity_uri.split("/")[-1].replace("_", " ")},
                    "incoming_relationships": [],
                    "outgoing_relationships": [],
                    "is_mock": True
                }
            
            # Build JSON-RPC request
            arguments = {
                "ontology_source": ontology_source,
                "entity_uri": entity_uri
            }
            
            if relationship_type:
                arguments["relationship_type"] = relationship_type
            
            jsonrpc_request = {
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "get_entity_relationships",
                    "arguments": arguments
                },
                "id": 1
            }
            
            # Send request to MCP server
            response = self.session.post(
                f"{self.mcp_url}/jsonrpc",
                json=jsonrpc_request,
                timeout=15
            )
            
            # Check response
            if response.status_code == 200:
                result = response.json()
                
                # Check for errors in the JSON-RPC response
                if "error" in result:
                    print(f"Error in JSON-RPC response: {result['error']}")
                    return {
                        "error": result["error"]["message"],
                        "incoming_relationships": [],
                        "outgoing_relationships": []
                    }
                
                # Parse the tool result
                if "result" in result and "content" in result["result"]:
                    content_text = result["result"]["content"][0]["text"]
                    return json.loads(content_text)
                else:
                    print(f"Unexpected response format: {result}")
                    return {
                        "error": "Unexpected response format",
                        "incoming_relationships": [],
                        "outgoing_relationships": []
                    }
            else:
                error_message = f"Error calling get_entity_relationships: {response.status_code} - {response.text}"
                print(error_message)
                return {
                    "error": error_message,
                    "incoming_relationships": [],
                    "outgoing_relationships": []
                }
        except Exception as e:
            error_message = f"Error in get_entity_relationships: {str(e)}"
            print(error_message)
            return {
                "error": error_message,
                "incoming_relationships": [],
                "outgoing_relationships": []
            }
    
    def navigate_entity_hierarchy(self, ontology_source: str, entity_uri: str, 
                                 direction: str = "both") -> Dict[str, Any]:
        """
        Navigate the class hierarchy of an entity.
        
        Args:
            ontology_source: Source of the ontology
            entity_uri: URI of the entity to navigate from
            direction: 'up' for parents, 'down' for children, 'both' for both
            
        Returns:
            Dictionary with parent and/or child entities
        """
        try:
            print(f"Navigating hierarchy for entity {entity_uri} in ontology {ontology_source}")
            
            # If server is not connected but fallback is enabled, return mock data
            if not self.base_client.is_connected and self.use_mock_fallback:
                print("MCP server not connected, using mock data for navigate_entity_hierarchy")
                return {
                    "entity": {"uri": entity_uri, "label": entity_uri.split("/")[-1].replace("_", " ")},
                    "parents": [],
                    "children": [],
                    "is_mock": True
                }
            
            # Build JSON-RPC request
            jsonrpc_request = {
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "navigate_entity_hierarchy",
                    "arguments": {
                        "ontology_source": ontology_source,
                        "entity_uri": entity_uri,
                        "direction": direction
                    }
                },
                "id": 1
            }
            
            # Send request to MCP server
            response = self.session.post(
                f"{self.mcp_url}/jsonrpc",
                json=jsonrpc_request,
                timeout=15
            )
            
            # Check response
            if response.status_code == 200:
                result = response.json()
                
                # Check for errors in the JSON-RPC response
                if "error" in result:
                    print(f"Error in JSON-RPC response: {result['error']}")
                    return {
                        "error": result["error"]["message"],
                        "parents": [],
                        "children": []
                    }
                
                # Parse the tool result
                if "result" in result and "content" in result["result"]:
                    content_text = result["result"]["content"][0]["text"]
                    return json.loads(content_text)
                else:
                    print(f"Unexpected response format: {result}")
                    return {
                        "error": "Unexpected response format",
                        "parents": [],
                        "children": []
                    }
            else:
                error_message = f"Error calling navigate_entity_hierarchy: {response.status_code} - {response.text}"
                print(error_message)
                return {
                    "error": error_message,
                    "parents": [],
                    "children": []
                }
        except Exception as e:
            error_message = f"Error in navigate_entity_hierarchy: {str(e)}"
            print(error_message)
            return {
                "error": error_message,
                "parents": [],
                "children": []
            }
    
    def check_constraint(self, ontology_source: str, entity_uri: str, constraint_type: str, 
                        constraint_data: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Check if an entity satisfies a constraint.
        
        Args:
            ontology_source: Source of the ontology
            entity_uri: URI of the entity to check
            constraint_type: Type of constraint to check (domain_range, cardinality, custom)
            constraint_data: Additional data needed for checking the constraint
            
        Returns:
            Constraint check result
        """
        try:
            print(f"Checking {constraint_type} constraint for entity {entity_uri} in ontology {ontology_source}")
            
            constraint_data = constraint_data or {}
            
            # If server is not connected but fallback is enabled, return mock data
            if not self.base_client.is_connected and self.use_mock_fallback:
                print("MCP server not connected, using mock data for check_constraint")
                return {
                    "is_valid": True,
                    "is_mock": True
                }
            
            # Build JSON-RPC request
            jsonrpc_request = {
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "check_constraint",
                    "arguments": {
                        "ontology_source": ontology_source,
                        "entity_uri": entity_uri,
                        "constraint_type": constraint_type,
                        "constraint_data": constraint_data
                    }
                },
                "id": 1
            }
            
            # Send request to MCP server
            response = self.session.post(
                f"{self.mcp_url}/jsonrpc",
                json=jsonrpc_request,
                timeout=15
            )
            
            # Check response
            if response.status_code == 200:
                result = response.json()
                
                # Check for errors in the JSON-RPC response
                if "error" in result:
                    print(f"Error in JSON-RPC response: {result['error']}")
                    return {
                        "error": result["error"]["message"],
                        "is_valid": False
                    }
                
                # Parse the tool result
                if "result" in result and "content" in result["result"]:
                    content_text = result["result"]["content"][0]["text"]
                    return json.loads(content_text)
                else:
                    print(f"Unexpected response format: {result}")
                    return {
                        "error": "Unexpected response format",
                        "is_valid": False
                    }
            else:
                error_message = f"Error calling check_constraint: {response.status_code} - {response.text}"
                print(error_message)
                return {
                    "error": error_message,
                    "is_valid": False
                }
        except Exception as e:
            error_message = f"Error in check_constraint: {str(e)}"
            print(error_message)
            return {
                "error": error_message,
                "is_valid": False
            }
    
    def search_entities(self, ontology_source: str, query: str, entity_type: Optional[str] = None, 
                      match_mode: str = "contains") -> Dict[str, Any]:
        """
        Search for entities by keywords or patterns.
        
        Args:
            ontology_source: Source of the ontology
            query: Text to search for
            entity_type: Optional type of entity to filter by
            match_mode: How to match (contains, exact, regex)
            
        Returns:
            Dictionary with matching entities
        """
        try:
            print(f"Searching for '{query}' in ontology {ontology_source}")
            
            # If server is not connected but fallback is enabled, return mock data
            if not self.base_client.is_connected and self.use_mock_fallback:
                print("MCP server not connected, using mock data for search_entities")
                return {
                    "entities": [],
                    "count": 0,
                    "query": query,
                    "is_mock": True
                }
            
            # Build JSON-RPC request
            arguments = {
                "ontology_source": ontology_source,
                "query": query,
                "match_mode": match_mode
            }
            
            if entity_type:
                arguments["entity_type"] = entity_type
            
            jsonrpc_request = {
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "search_entities",
                    "arguments": arguments
                },
                "id": 1
            }
            
            # Send request to MCP server
            response = self.session.post(
                f"{self.mcp_url}/jsonrpc",
                json=jsonrpc_request,
                timeout=15
            )
            
            # Check response
            if response.status_code == 200:
                result = response.json()
                
                # Check for errors in the JSON-RPC response
                if "error" in result:
                    print(f"Error in JSON-RPC response: {result['error']}")
                    return {
                        "error": result["error"]["message"],
                        "entities": [],
                        "count": 0,
                        "query": query
                    }
                
                # Parse the tool result
                if "result" in result and "content" in result["result"]:
                    content_text = result["result"]["content"][0]["text"]
                    return json.loads(content_text)
                else:
                    print(f"Unexpected response format: {result}")
                    return {
                        "error": "Unexpected response format",
                        "entities": [],
                        "count": 0,
                        "query": query
                    }
            else:
                error_message = f"Error calling search_entities: {response.status_code} - {response.text}"
                print(error_message)
                return {
                    "error": error_message,
                    "entities": [],
                    "count": 0,
                    "query": query
                }
        except Exception as e:
            error_message = f"Error in search_entities: {str(e)}"
            print(error_message)
            return {
                "error": error_message,
                "entities": [],
                "count": 0,
                "query": query
            }
    
    def get_entity_details(self, ontology_source: str, entity_uri: str) -> Dict[str, Any]:
        """
        Get comprehensive information about an entity.
        
        Args:
            ontology_source: Source of the ontology
            entity_uri: URI of the entity to get details for
            
        Returns:
            Dictionary with entity details
        """
        try:
            print(f"Getting details for entity {entity_uri} in ontology {ontology_source}")
            
            # If server is not connected but fallback is enabled, return mock data
            if not self.base_client.is_connected and self.use_mock_fallback:
                print("MCP server not connected, using mock data for get_entity_details")
                return {
                    "uri": entity_uri,
                    "label": entity_uri.split("/")[-1].replace("_", " "),
                    "description": None,
                    "types": [],
                    "properties": [],
                    "parents": [],
                    "children": [],
                    "is_mock": True
                }
            
            # Build JSON-RPC request
            jsonrpc_request = {
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "get_entity_details",
                    "arguments": {
                        "ontology_source": ontology_source,
                        "entity_uri": entity_uri
                    }
                },
                "id": 1
            }
            
            # Send request to MCP server
            response = self.session.post(
                f"{self.mcp_url}/jsonrpc",
                json=jsonrpc_request,
                timeout=15
            )
            
            # Check response
            if response.status_code == 200:
                result = response.json()
                
                # Check for errors in the JSON-RPC response
                if "error" in result:
                    print(f"Error in JSON-RPC response: {result['error']}")
                    return {
                        "error": result["error"]["message"],
                        "uri": entity_uri,
                        "label": entity_uri.split("/")[-1].replace("_", " ")
                    }
                
                # Parse the tool result
                if "result" in result and "content" in result["result"]:
                    content_text = result["result"]["content"][0]["text"]
                    return json.loads(content_text)
                else:
                    print(f"Unexpected response format: {result}")
                    return {
                        "error": "Unexpected response format",
                        "uri": entity_uri,
                        "label": entity_uri.split("/")[-1].replace("_", " ")
                    }
            else:
                error_message = f"Error calling get_entity_details: {response.status_code} - {response.text}"
                print(error_message)
                return {
                    "error": error_message,
                    "uri": entity_uri,
                    "label": entity_uri.split("/")[-1].replace("_", " ")
                }
        except Exception as e:
            error_message = f"Error in get_entity_details: {str(e)}"
            print(error_message)
            return {
                "error": error_message,
                "uri": entity_uri,
                "label": entity_uri.split("/")[-1].replace("_", " ")
            }
    
    def get_ontology_guidelines(self, ontology_source: str) -> Dict[str, Any]:
        """
        Get guidelines and principles from an ontology.
        
        Args:
            ontology_source: Source of the ontology
            
        Returns:
            Dictionary with guidelines and principles
        """
        try:
            print(f"Getting guidelines for ontology {ontology_source}")
            
            # If server is not connected but fallback is enabled, return mock data
            if not self.base_client.is_connected and self.use_mock_fallback:
                print("MCP server not connected, using mock data for get_ontology_guidelines")
                return {
                    "guidelines": [],
                    "count": 0,
                    "ontology_source": ontology_source,
                    "is_mock": True
                }
            
            # Build JSON-RPC request
            jsonrpc_request = {
                "jsonrpc": "2.0",
                "method": "call_tool",
                "params": {
                    "name": "get_ontology_guidelines",
                    "arguments": {
                        "ontology_source": ontology_source
                    }
                },
                "id": 1
            }
            
            # Send request to MCP server
            response = self.session.post(
                f"{self.mcp_url}/jsonrpc",
                json=jsonrpc_request,
                timeout=15
            )
            
            # Check response
            if response.status_code == 200:
                result = response.json()
                
                # Check for errors in the JSON-RPC response
                if "error" in result:
                    print(f"Error in JSON-RPC response: {result['error']}")
                    return {
                        "error": result["error"]["message"],
                        "guidelines": [],
                        "count": 0,
                        "ontology_source": ontology_source
                    }
                
                # Parse the tool result
                if "result" in result and "content" in result["result"]:
                    content_text = result["result"]["content"][0]["text"]
                    return json.loads(content_text)
                else:
                    print(f"Unexpected response format: {result}")
                    return {
                        "error": "Unexpected response format",
                        "guidelines": [],
                        "count": 0,
                        "ontology_source": ontology_source
                    }
            else:
                error_message = f"Error calling get_ontology_guidelines: {response.status_code} - {response.text}"
                print(error_message)
                return {
                    "error": error_message,
                    "guidelines": [],
                    "count": 0,
                    "ontology_source": ontology_source
                }
        except Exception as e:
            error_message = f"Error in get_ontology_guidelines: {str(e)}"
            print(error_message)
            return {
                "error": error_message,
                "guidelines": [],
                "count": 0,
                "ontology_source": ontology_source
            }
    
    def format_entity_for_context(self, entity: Dict[str, Any]) -> str:
        """
        Format an entity dictionary into a readable string for context.
        
        Args:
            entity: Entity dictionary from get_entity_details()
            
        Returns:
            Formatted string representation
        """
        if not entity:
            return "No entity data available"
        
        if "error" in entity:
            return f"Error retrieving entity: {entity['error']}"
        
        result = []
        result.append(f"# {entity.get('label', 'Unknown Entity')}")
        
        if entity.get('description'):
            result.append(f"\n{entity['description']}")
        
        if entity.get('types'):
            type_labels = [t.get('label', t.get('uri', 'Unknown')).split('/')[-1].replace('_', ' ')
                         for t in entity['types']]
            result.append(f"\nTypes: {', '.join(type_labels)}")
        
        if entity.get('parents'):
            parent_labels = [p.get('label', p.get('uri', 'Unknown')).split('/')[-1].replace('_', ' ')
                           for p in entity['parents']]
            if parent_labels:
                result.append(f"\nParent Classes: {', '.join(parent_labels)}")
        
        if entity.get('properties'):
            result.append("\nProperties:")
            for prop in entity['properties']:
                pred_label = prop.get('predicate', {}).get('label', 'Unknown')
                
                if prop.get('object', {}).get('is_literal', True):
                    obj_value = prop.get('object', {}).get('value', 'Unknown')
                    result.append(f"- {pred_label}: {obj_value}")
                else:
                    obj_label = prop.get('object', {}).get('label', 'Unknown')
                    result.append(f"- {pred_label}: {obj_label}")
        
        if entity.get('capabilities'):
            result.append("\nCapabilities:")
            for cap in entity['capabilities']:
                cap_label = cap.get('label', 'Unknown')
                cap_desc = cap.get('description', '')
                result.append(f"- {cap_label}: {cap_desc}")
        
        return "\n".join(result)
    
    def format_relationships_for_context(self, relationships: Dict[str, Any]) -> str:
        """
        Format relationships dictionary into a readable string for context.
        
        Args:
            relationships: Relationships dictionary from get_entity_relationships()
            
        Returns:
            Formatted string representation
        """
        if not relationships:
            return "No relationship data available"
        
        if "error" in relationships:
            return f"Error retrieving relationships: {relationships['error']}"
        
        result = []
        entity_label = relationships.get('entity', {}).get('label', 'Unknown Entity')
        result.append(f"# Relationships for {entity_label}")
        
        incoming = relationships.get('incoming_relationships', [])
        if incoming:
            result.append("\n## Incoming Relationships:")
            for rel in incoming:
                subj_label = rel.get('subject', {}).get('label', 'Unknown')
                pred_label = rel.get('predicate', {}).get('label', 'Unknown')
                result.append(f"- {subj_label} {pred_label} {entity_label}")
        else:
            result.append("\n## Incoming Relationships: None")
        
        outgoing = relationships.get('outgoing_relationships', [])
        if outgoing:
            result.append("\n## Outgoing Relationships:")
            for rel in outgoing:
                pred_label = rel.get('predicate', {}).get('label', 'Unknown')
                
                if rel.get('object', {}).get('is_literal', True):
                    obj_value = rel.get('object', {}).get('value', 'Unknown')
                    result.append(f"- {entity_label} {pred_label} {obj_value}")
                else:
                    obj_label = rel.get('object', {}).get('label', 'Unknown')
                    result.append(f"- {entity_label} {pred_label} {obj_label}")
        else:
            result.append("\n## Outgoing Relationships: None")
        
        return "\n".join(result)
    
    def format_guidelines_for_context(self, guidelines_data: Dict[str, Any]) -> str:
        """
        Format guidelines dictionary into a readable string for context.
        
        Args:
            guidelines_data: Guidelines dictionary from get_ontology_guidelines()
            
        Returns:
            Formatted string representation
        """
        if not guidelines_data:
            return "No guideline data available"
        
        if "error" in guidelines_data:
            return f"Error retrieving guidelines: {guidelines_data['error']}"
        
        result = []
        ontology_source = guidelines_data.get('ontology_source', 'Unknown Ontology')
        result.append(f"# Guidelines for {ontology_source}")
        
        guidelines = guidelines_data.get('guidelines', [])
        if not guidelines:
            result.append("\nNo guidelines found in this ontology.")
            return "\n".join(result)
        
        for guideline in guidelines:
            label = guideline.get('label', 'Unnamed Guideline')
            description = guideline.get('description', '')
            
            result.append(f"\n## {label}")
            if description:
                result.append(description)
        
        return "\n".join(result)


# Utility function to get enhanced MCP client instance
def get_enhanced_mcp_client() -> EnhancedMCPClient:
    """Get the singleton instance of EnhancedMCPClient."""
    return EnhancedMCPClient.get_instance()
