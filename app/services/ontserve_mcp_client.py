"""
OntServe MCP Client for ProEthica

Enables ProEthica to call MCP tools on OntServe server for real-time ontology exploration
during concept extraction. Delegates to MCPTransport (MCP Streamable HTTP).
"""

import logging
from typing import Dict, List
import os

from app.services.mcp_transport import MCPTransport, MCPTransportError, get_mcp_transport

logger = logging.getLogger(__name__)


class MCPClientError(Exception):
    """Exception raised by MCP client operations."""
    pass


class OntServeMCPClient:
    """
    MCP client for communicating with OntServe MCP server.

    Provides tools for ontology exploration during concept extraction:
    - get_entities_by_category: Explore existing concepts by category
    - sparql_query: Execute SPARQL queries on the ontology
    - submit_candidate_concept: Submit new concepts for review
    """

    def __init__(self, mcp_url: str = None, timeout: int = 30):
        self.mcp_url = mcp_url or os.environ.get('ONTSERVE_MCP_URL', 'http://localhost:8082')
        self._transport = MCPTransport(base_url=self.mcp_url, timeout=timeout) if mcp_url else get_mcp_transport()
        logger.info(f"OntServe MCP client initialized: {self.mcp_url}")

    def get_entities_by_category_sync(self, category: str, domain_id: str = "proethica-intermediate",
                                    status: str = "approved") -> Dict:
        try:
            return self._transport.call_tool("get_entities_by_category", {
                "category": category,
                "domain_id": domain_id,
                "status": status,
            })
        except MCPTransportError as e:
            raise MCPClientError(str(e)) from e

    def get_all_categories_sync(self, domain_id: str = "proethica-intermediate") -> Dict[str, List[Dict]]:
        categories = ["Role", "Principle", "Obligation", "State", "Resource",
                     "Action", "Event", "Capability", "Constraint"]

        all_entities = {}
        for category in categories:
            try:
                result = self.get_entities_by_category_sync(category, domain_id)
                all_entities[category] = result.get("entities", [])
            except Exception as e:
                logger.warning(f"Failed to get {category} entities: {e}")
                all_entities[category] = []

        return all_entities

    def sparql_query_sync(self, query: str, domain_id: str = "proethica-intermediate") -> Dict:
        try:
            return self._transport.call_tool("sparql_query", {
                "query": query,
                "domain_id": domain_id,
            })
        except MCPTransportError as e:
            raise MCPClientError(str(e)) from e


# Singleton instance
_ontserve_mcp_client_instance = None

def get_ontserve_mcp_client() -> OntServeMCPClient:
    """Get singleton OntServe MCP client instance."""
    global _ontserve_mcp_client_instance
    if _ontserve_mcp_client_instance is None:
        _ontserve_mcp_client_instance = OntServeMCPClient()
    return _ontserve_mcp_client_instance


# Tool definitions for Anthropic API integration (used by guideline_analysis_service)
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
