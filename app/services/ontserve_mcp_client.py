"""
OntServe MCP Client for ProEthica

Enables ProEthica to call MCP tools on OntServe server for real-time ontology exploration
during concept extraction. Provides both sync and async interfaces.
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class OntServeMCPClient:
    """
    MCP client for communicating with OntServe MCP server.
    
    Provides tools for ontology exploration during concept extraction:
    - get_entities_by_category: Explore existing concepts by category
    - sparql_query: Execute SPARQL queries on the ontology
    - submit_candidate_concept: Submit new concepts for review
    """
    
    def __init__(self, mcp_url: str = None, timeout: int = 30, max_retries: int = 3):
        """
        Initialize OntServe MCP client.
        
        Args:
            mcp_url: OntServe MCP server URL (defaults to environment variable)
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.mcp_url = mcp_url or os.environ.get('ONTSERVE_MCP_URL', 'http://localhost:8082')
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = None
        self._request_id = 1
        
        logger.info(f"OntServe MCP client initialized: {self.mcp_url}")
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def _make_request(self, method: str, params: Dict = None) -> Dict:
        """
        Make JSON-RPC request to MCP server.
        
        Args:
            method: JSON-RPC method name
            params: Method parameters
            
        Returns:
            JSON-RPC response result
            
        Raises:
            MCPClientError: On request failure or server error
        """
        session = await self._get_session()
        
        request_data = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {}
        }
        self._request_id += 1
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with session.post(self.mcp_url, json=request_data) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        if "error" in result:
                            raise MCPClientError(f"MCP server error: {result['error']}")
                        
                        return result.get("result", {})
                    else:
                        error_text = await response.text()
                        raise MCPClientError(f"HTTP {response.status}: {error_text}")
                        
            except aiohttp.ClientError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    continue
                else:
                    break
            except Exception as e:
                last_error = e
                break
        
        raise MCPClientError(f"Request failed after {self.max_retries} attempts: {last_error}")
    
    async def call_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """
        Call an MCP tool on the server.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments
            
        Returns:
            Tool execution result
        """
        logger.debug(f"Calling MCP tool: {tool_name} with args: {arguments}")
        
        result = await self._make_request("call_tool", {
            "name": tool_name,
            "arguments": arguments
        })
        
        # Extract text content from MCP response format
        if isinstance(result, dict) and "content" in result:
            content = result["content"]
            if isinstance(content, list) and len(content) > 0:
                text_content = content[0].get("text", "")
                try:
                    return json.loads(text_content)
                except json.JSONDecodeError:
                    return {"text": text_content}
        
        return result
    
    async def get_entities_by_category(self, category: str, domain_id: str = "proethica-intermediate", 
                                     status: str = "approved") -> Dict:
        """
        Get ontology entities by category.
        
        Args:
            category: Entity category (Role, Principle, Obligation, etc.)
            domain_id: Professional domain identifier
            status: Concept status filter
            
        Returns:
            Dict with entities list and metadata
        """
        return await self.call_tool("get_entities_by_category", {
            "category": category,
            "domain_id": domain_id,
            "status": status
        })
    
    async def sparql_query(self, query: str, domain_id: str = "proethica-intermediate") -> Dict:
        """
        Execute SPARQL query on ontology.
        
        Args:
            query: SPARQL query string
            domain_id: Professional domain identifier
            
        Returns:
            SPARQL query results
        """
        return await self.call_tool("sparql_query", {
            "query": query,
            "domain_id": domain_id
        })
    
    async def submit_candidate_concept(self, concept: Dict, domain_id: str = "proethica-intermediate",
                                     submitted_by: str = "proethica-extractor") -> Dict:
        """
        Submit a candidate concept for review.
        
        Args:
            concept: Concept data (label, category, description, uri, etc.)
            domain_id: Professional domain identifier
            submitted_by: User/system submitting the concept
            
        Returns:
            Submission result
        """
        return await self.call_tool("submit_candidate_concept", {
            "concept": concept,
            "domain_id": domain_id,
            "submitted_by": submitted_by
        })
    
    async def get_all_categories(self, domain_id: str = "proethica-intermediate") -> Dict[str, List[Dict]]:
        """
        Get entities for all ProEthica categories.
        
        Args:
            domain_id: Professional domain identifier
            
        Returns:
            Dict mapping category names to entity lists
        """
        categories = ["Role", "Principle", "Obligation", "State", "Resource", 
                     "Action", "Event", "Capability", "Constraint"]
        
        all_entities = {}
        for category in categories:
            try:
                result = await self.get_entities_by_category(category, domain_id)
                all_entities[category] = result.get("entities", [])
                logger.debug(f"Found {len(all_entities[category])} {category} entities")
            except Exception as e:
                logger.warning(f"Failed to get {category} entities: {e}")
                all_entities[category] = []
        
        return all_entities
    
    async def close(self):
        """Close the aiohttp session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    # Sync interface for compatibility with existing code
    def get_entities_by_category_sync(self, category: str, domain_id: str = "proethica-intermediate",
                                    status: str = "approved") -> Dict:
        """Sync wrapper for get_entities_by_category."""
        return self._run_async_safe(self.get_entities_by_category(category, domain_id, status))
    
    def get_all_categories_sync(self, domain_id: str = "proethica-intermediate") -> Dict[str, List[Dict]]:
        """Sync wrapper for get_all_categories."""
        return self._run_async_safe(self.get_all_categories(domain_id))
    
    def sparql_query_sync(self, query: str, domain_id: str = "proethica-intermediate") -> Dict:
        """Sync wrapper for sparql_query."""
        return self._run_async_safe(self.sparql_query(query, domain_id))
    
    def _run_async_safe(self, coro):
        """Safely run async coroutine in sync context, handling existing event loops."""
        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Event loop is running, we need to use a thread
                import concurrent.futures
                import threading
                
                def run_in_thread():
                    new_loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(new_loop)
                    try:
                        return new_loop.run_until_complete(coro)
                    finally:
                        new_loop.close()
                
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(run_in_thread)
                    return future.result(timeout=self.timeout)
            else:
                # No loop running, can use normal run
                return loop.run_until_complete(coro)
        except RuntimeError:
            # No event loop exists, create one
            return asyncio.run(coro)
        except Exception as e:
            logger.error(f"Error running async operation: {e}")
            raise MCPClientError(f"Failed to execute async operation: {e}")


class MCPClientError(Exception):
    """Exception raised by MCP client operations."""
    pass


# Singleton instance for easy access
_ontserve_mcp_client_instance = None

def get_ontserve_mcp_client() -> OntServeMCPClient:
    """Get singleton OntServe MCP client instance."""
    global _ontserve_mcp_client_instance
    if _ontserve_mcp_client_instance is None:
        _ontserve_mcp_client_instance = OntServeMCPClient()
    return _ontserve_mcp_client_instance


# Tool definitions for Anthropic API integration
ONTSERVE_MCP_TOOLS = [
    {
        "name": "explore_ontology_category",
        "description": "Explore existing concepts in a specific ontology category before extracting new concepts",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Ontology category to explore",
                    "enum": ["Role", "Principle", "Obligation", "State", "Resource", 
                            "Action", "Event", "Capability", "Constraint"]
                },
                "domain_id": {
                    "type": "string",
                    "description": "Professional domain identifier",
                    "default": "proethica-intermediate"
                }
            },
            "required": ["category"]
        }
    },
    {
        "name": "query_ontology_relationships",
        "description": "Query relationships between concepts in the ontology",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "SPARQL query to find relationships"
                },
                "domain_id": {
                    "type": "string",
                    "description": "Professional domain identifier",
                    "default": "proethica-intermediate"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "check_concept_exists",
        "description": "Check if a concept already exists in the ontology",
        "input_schema": {
            "type": "object",
            "properties": {
                "concept_label": {
                    "type": "string",
                    "description": "Label of the concept to check"
                },
                "category": {
                    "type": "string",
                    "description": "Category to search in",
                    "enum": ["Role", "Principle", "Obligation", "State", "Resource", 
                            "Action", "Event", "Capability", "Constraint"]
                },
                "domain_id": {
                    "type": "string",
                    "description": "Professional domain identifier",
                    "default": "proethica-intermediate"
                }
            },
            "required": ["concept_label", "category"]
        }
    }
]


# Mock MCP client for testing when server is unavailable
class MockOntServeMCPClient(OntServeMCPClient):
    """Mock MCP client that returns sample data when server is unavailable."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("Using mock MCP client - server unavailable")
    
    async def get_entities_by_category(self, category: str, domain_id: str = "proethica-intermediate",
                                     status: str = "approved") -> Dict:
        """Return mock entities for testing."""
        mock_entities = {
            "Role": [
                {"uri": "http://proethica.org/ontology/intermediate#EngineerRole", 
                 "label": "Engineer Role", "description": "Professional engineer"},
                {"uri": "http://proethica.org/ontology/intermediate#ClientRole",
                 "label": "Client Role", "description": "Client representative"}
            ],
            "Principle": [
                {"uri": "http://proethica.org/ontology/intermediate#SafetyPrinciple",
                 "label": "Safety Principle", "description": "Public safety principle"},
                {"uri": "http://proethica.org/ontology/intermediate#IntegrityPrinciple", 
                 "label": "Integrity Principle", "description": "Professional integrity"}
            ],
            "Obligation": [
                {"uri": "http://proethica.org/ontology/intermediate#CompetenceObligation",
                 "label": "Competence Obligation", "description": "Duty to maintain competence"}
            ]
        }
        
        return {
            "entities": mock_entities.get(category, []),
            "category": category,
            "domain_id": domain_id,
            "status": status,
            "total_count": len(mock_entities.get(category, [])),
            "is_mock": True
        }
    
    async def sparql_query(self, query: str, domain_id: str = "proethica-intermediate") -> Dict:
        """Return mock SPARQL results."""
        return {
            "bindings": [],
            "query": query,
            "domain_id": domain_id,
            "execution_time_ms": 10,
            "is_mock": True,
            "message": "Mock SPARQL execution - server unavailable"
        }


class MCPClientError(Exception):
    """Exception raised by MCP client operations."""
    pass


# Singleton instance for easy access
_ontserve_mcp_client_instance = None

def get_ontserve_mcp_client() -> OntServeMCPClient:
    """Get singleton OntServe MCP client instance."""
    global _ontserve_mcp_client_instance
    if _ontserve_mcp_client_instance is None:
        _ontserve_mcp_client_instance = OntServeMCPClient()
    return _ontserve_mcp_client_instance


# Tool definitions for Anthropic API integration
ONTSERVE_MCP_TOOLS = [
    {
        "name": "explore_ontology_category",
        "description": "Explore existing concepts in a specific ontology category before extracting new concepts",
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Ontology category to explore",
                    "enum": ["Role", "Principle", "Obligation", "State", "Resource", 
                            "Action", "Event", "Capability", "Constraint"]
                },
                "domain_id": {
                    "type": "string",
                    "description": "Professional domain identifier",
                    "default": "proethica-intermediate"
                }
            },
            "required": ["category"]
        }
    },
    {
        "name": "query_ontology_relationships",
        "description": "Query relationships between concepts in the ontology",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "SPARQL query to find relationships"
                },
                "domain_id": {
                    "type": "string",
                    "description": "Professional domain identifier",
                    "default": "proethica-intermediate"
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "check_concept_exists",
        "description": "Check if a concept already exists in the ontology",
        "input_schema": {
            "type": "object",
            "properties": {
                "concept_label": {
                    "type": "string",
                    "description": "Label of the concept to check"
                },
                "category": {
                    "type": "string",
                    "description": "Category to search in",
                    "enum": ["Role", "Principle", "Obligation", "State", "Resource", 
                            "Action", "Event", "Capability", "Constraint"]
                },
                "domain_id": {
                    "type": "string",
                    "description": "Professional domain identifier",
                    "default": "proethica-intermediate"
                }
            },
            "required": ["concept_label", "category"]
        }
    }
]
