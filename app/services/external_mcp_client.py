"""
External MCP Client - Connects to OntServe MCP server.
Uses MCP Streamable HTTP transport (FastMCP 3.x compatible).
"""

import json
import logging
from typing import Dict, List, Any, Optional

from app.services.mcp_transport import MCPTransport, MCPTransportError

logger = logging.getLogger(__name__)


class ExternalMCPClient:
    """Client for OntServe MCP server tools."""

    def __init__(self, server_url: str = None):
        self.transport = MCPTransport(base_url=server_url)
        logger.info(f"ExternalMCPClient initialized for: {self.transport.base_url}")

    def list_tools(self) -> Dict[str, Any]:
        """List available MCP tools."""
        try:
            tools = self.transport.list_tools()
            logger.info(f"Listed {len(tools)} MCP tools")
            return {'success': True, 'tools': tools}
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            return {'success': False, 'error': str(e)}

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call an MCP tool."""
        try:
            result = self.transport.call_tool(tool_name, arguments)
            logger.debug(f"Tool '{tool_name}' executed successfully")
            return {'success': True, 'result': result}
        except MCPTransportError as e:
            logger.error(f"Tool '{tool_name}' failed: {e}")
            return {'success': False, 'error': str(e)}
        except Exception as e:
            logger.error(f"Error calling tool '{tool_name}': {e}")
            return {'success': False, 'error': str(e)}

    def get_entities_by_category(
        self, category: str, domain_id: str = "engineering-ethics"
    ) -> Dict[str, Any]:
        """Get ontology entities by category."""
        return self.call_tool("get_entities_by_category", {
            "category": category,
            "domain_id": domain_id,
            "status": "approved",
        })

    def _get_entities(self, category: str, domain_id: str) -> List[Dict[str, Any]]:
        """Shared helper for get_all_*_entities methods."""
        result = self.get_entities_by_category(category, domain_id)
        if result.get('success') and result.get('result'):
            entities = result['result'].get('entities', [])
            logger.info(f"Retrieved {len(entities)} {category} entities")
            return entities
        logger.warning(f"No {category} entities found or query failed")
        return []

    def get_all_role_entities(self, domain_id: str = "engineering-ethics") -> List[Dict]:
        return self._get_entities("Role", domain_id)

    def get_all_principle_entities(self, domain_id: str = "engineering-ethics") -> List[Dict]:
        return self._get_entities("Principle", domain_id)

    def get_all_obligation_entities(self, domain_id: str = "engineering-ethics") -> List[Dict]:
        return self._get_entities("Obligation", domain_id)

    def get_all_state_entities(self, domain_id: str = "engineering-ethics") -> List[Dict]:
        return self._get_entities("State", domain_id)

    def get_all_resource_entities(self, domain_id: str = "engineering-ethics") -> List[Dict]:
        return self._get_entities("Resource", domain_id)

    def get_all_constraint_entities(self, domain_id: str = "engineering-ethics") -> List[Dict]:
        return self._get_entities("Constraint", domain_id)

    def get_all_capability_entities(self, domain_id: str = "engineering-ethics") -> List[Dict]:
        return self._get_entities("Capability", domain_id)

    def get_all_action_entities(self, domain_id: str = "engineering-ethics") -> List[Dict]:
        return self._get_entities("Action", domain_id)

    def get_all_event_entities(self, domain_id: str = "engineering-ethics") -> List[Dict]:
        return self._get_entities("Event", domain_id)

    def submit_candidate_concept(
        self, concept: Dict[str, Any], domain_id: str = "engineering-ethics"
    ) -> Dict[str, Any]:
        """Submit a candidate concept."""
        return self.call_tool("submit_candidate_concept", {
            "concept": concept,
            "domain_id": domain_id,
            "submitted_by": "proethica-external-extraction",
        })

    def get_domain_info(self, domain_id: str = "engineering-ethics") -> Dict[str, Any]:
        """Get domain information."""
        return self.call_tool("get_domain_info", {"domain_id": domain_id})

    def health_check(self) -> Dict[str, Any]:
        """Check if the MCP server is healthy."""
        data = self.transport.health_check()
        ok = data.get("status") == "ok"
        return {'success': ok, 'data': data} if ok else {'success': False, 'error': str(data)}


# Module-level singleton
_external_mcp_client = None


def get_external_mcp_client() -> ExternalMCPClient:
    """Get or create global ExternalMCPClient instance."""
    global _external_mcp_client
    if _external_mcp_client is None:
        _external_mcp_client = ExternalMCPClient()
    return _external_mcp_client
