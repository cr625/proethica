"""
OntServe MCP Client for ProEthica

Enables ProEthica to call MCP tools on OntServe server for real-time ontology exploration
during concept extraction. Provides both sync and async interfaces.

Sync methods delegate to MCPTransport (MCP Streamable HTTP).
Async methods use aiohttp with MCP Streamable HTTP protocol.
"""

import asyncio
import aiohttp
import json
import logging
from typing import Dict, List, Any, Optional
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

    def __init__(self, mcp_url: str = None, timeout: int = 30, max_retries: int = 3):
        self.mcp_url = mcp_url or os.environ.get('ONTSERVE_MCP_URL', 'http://localhost:8082')
        self.timeout = timeout
        self.max_retries = max_retries
        self._transport = MCPTransport(base_url=self.mcp_url, timeout=timeout)

        # Async state
        self.session = None
        self._mcp_session_id = None
        self._mcp_initialized = False
        self._request_id = 1

        logger.info(f"OntServe MCP client initialized: {self.mcp_url}")

    # ── Async interface (MCP Streamable HTTP) ──────────────────────

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def _make_request(self, method: str, params: Dict = None) -> Dict:
        """Make MCP Streamable HTTP request (POST to /mcp, SSE response)."""
        session = await self._get_session()
        self._request_id += 1

        payload = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
            "params": params or {},
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._mcp_session_id:
            headers["Mcp-Session-Id"] = self._mcp_session_id

        last_error = None
        for attempt in range(self.max_retries):
            try:
                async with session.post(
                    f"{self.mcp_url.rstrip('/')}/mcp",
                    json=payload,
                    headers=headers,
                ) as response:
                    # Capture session ID
                    sid = response.headers.get("Mcp-Session-Id")
                    if sid:
                        self._mcp_session_id = sid

                    if response.status != 200:
                        error_text = await response.text()
                        raise MCPClientError(f"HTTP {response.status}: {error_text}")

                    # Parse SSE or plain JSON
                    ct = response.headers.get("content-type", "")
                    if "text/event-stream" in ct:
                        text = await response.text()
                        for line in text.splitlines():
                            if line.startswith("data: "):
                                result = json.loads(line[6:])
                                break
                        else:
                            raise MCPClientError("No data line in SSE response")
                    else:
                        result = await response.json()

                    if "error" in result:
                        raise MCPClientError(f"MCP error: {result['error']}")

                    return result.get("result", {})

            except aiohttp.ClientError as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
            except MCPClientError:
                raise
            except Exception as e:
                last_error = e
                break

        raise MCPClientError(f"Request failed after {self.max_retries} attempts: {last_error}")

    async def _ensure_initialized(self):
        """Send MCP initialize handshake if not yet done."""
        if not self._mcp_initialized:
            await self._make_request("initialize", {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "proethica-ontserve-client", "version": "1.0"},
            })
            self._mcp_initialized = True

    async def call_tool(self, tool_name: str, arguments: Dict) -> Dict:
        """Call an MCP tool on the server (async)."""
        logger.debug(f"Calling MCP tool: {tool_name} with args: {arguments}")
        await self._ensure_initialized()

        result = await self._make_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
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
        return await self.call_tool("get_entities_by_category", {
            "category": category,
            "domain_id": domain_id,
            "status": status,
        })

    async def sparql_query(self, query: str, domain_id: str = "proethica-intermediate") -> Dict:
        return await self.call_tool("sparql_query", {
            "query": query,
            "domain_id": domain_id,
        })

    async def submit_candidate_concept(self, concept: Dict, domain_id: str = "proethica-intermediate",
                                     submitted_by: str = "proethica-extractor") -> Dict:
        return await self.call_tool("submit_candidate_concept", {
            "concept": concept,
            "domain_id": domain_id,
            "submitted_by": submitted_by,
        })

    async def get_all_categories(self, domain_id: str = "proethica-intermediate") -> Dict[str, List[Dict]]:
        categories = ["Role", "Principle", "Obligation", "State", "Resource",
                     "Action", "Event", "Capability", "Constraint"]

        all_entities = {}
        for category in categories:
            try:
                result = await self.get_entities_by_category(category, domain_id)
                all_entities[category] = result.get("entities", [])
            except Exception as e:
                logger.warning(f"Failed to get {category} entities: {e}")
                all_entities[category] = []

        return all_entities

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    # ── Sync interface (delegates to MCPTransport) ─────────────────

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


# Mock MCP client for testing when server is unavailable
class MockOntServeMCPClient(OntServeMCPClient):
    """Mock MCP client that returns sample data when server is unavailable."""

    def __init__(self, *args, **kwargs):
        # Skip parent __init__ to avoid creating real transport
        self.mcp_url = "mock://localhost"
        self.timeout = 30
        self.max_retries = 1
        self._transport = None
        self.session = None
        self._mcp_session_id = None
        self._mcp_initialized = False
        self._request_id = 1
        logger.info("Using mock MCP client - server unavailable")

    async def get_entities_by_category(self, category: str, domain_id: str = "proethica-intermediate",
                                     status: str = "approved") -> Dict:
        mock_entities = {
            "Role": [
                {"uri": "http://proethica.org/ontology/intermediate#EngineerRole",
                 "label": "Engineer Role", "description": "Professional engineer"},
            ],
            "Principle": [
                {"uri": "http://proethica.org/ontology/intermediate#SafetyPrinciple",
                 "label": "Safety Principle", "description": "Public safety principle"},
            ],
        }
        return {
            "entities": mock_entities.get(category, []),
            "category": category,
            "domain_id": domain_id,
            "total_count": len(mock_entities.get(category, [])),
            "is_mock": True,
        }

    async def sparql_query(self, query: str, domain_id: str = "proethica-intermediate") -> Dict:
        return {
            "bindings": [],
            "query": query,
            "domain_id": domain_id,
            "is_mock": True,
        }
