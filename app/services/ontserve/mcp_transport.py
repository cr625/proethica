"""
MCP Streamable HTTP Transport

Sync client for communicating with a FastMCP server over Streamable HTTP.
Handles session initialization, SSE response parsing, and tool dispatch.

Used by all ProEthica services that call OntServe MCP tools.
"""

import json
import logging
import os
import requests
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

MCP_PROTOCOL_VERSION = "2024-11-05"


class MCPTransportError(Exception):
    pass


class MCPTransport:
    """Sync transport for MCP Streamable HTTP servers."""

    def __init__(self, base_url: Optional[str] = None, timeout: int = 30):
        self.base_url = (
            base_url
            or os.environ.get("ONTSERVE_MCP_URL")
            or "http://localhost:8082"
        ).rstrip("/")
        self.mcp_endpoint = f"{self.base_url}/mcp"
        self.timeout = timeout
        self._session = requests.Session()
        self._session_id: Optional[str] = None
        self._request_id = 0
        self._initialized = False

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _send(self, method: str, params: Optional[dict] = None) -> dict:
        """Send a JSON-RPC request to the MCP endpoint, parse SSE response."""
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": method,
            "params": params or {},
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id

        response = self._session.post(
            self.mcp_endpoint,
            json=payload,
            headers=headers,
            timeout=self.timeout,
        )

        # Capture session ID
        session_id = response.headers.get("Mcp-Session-Id")
        if session_id:
            self._session_id = session_id

        if response.status_code != 200:
            raise MCPTransportError(
                f"MCP server returned HTTP {response.status_code}"
            )

        # Parse response: SSE or plain JSON
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            return self._parse_sse(response.text)
        return response.json()

    @staticmethod
    def _parse_sse(text: str) -> dict:
        """Extract JSON-RPC result from SSE response."""
        for line in text.splitlines():
            if line.startswith("data: "):
                return json.loads(line[6:])
        raise MCPTransportError("No data line in SSE response")

    def initialize(self) -> dict:
        """Send MCP initialize handshake."""
        result = self._send("initialize", {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "proethica", "version": "1.0"},
        })
        if "result" in result:
            self._initialized = True
        return result

    def _ensure_initialized(self):
        if not self._initialized:
            self.initialize()

    def list_tools(self) -> list:
        """List available MCP tools. Returns list of tool dicts."""
        self._ensure_initialized()
        result = self._send("tools/list", {})
        return result.get("result", {}).get("tools", [])

    def call_tool(self, name: str, arguments: dict) -> dict:
        """Call an MCP tool and return the parsed result dict.

        Returns the deserialized tool output (the JSON object the tool returned),
        not the MCP protocol wrapper.
        """
        self._ensure_initialized()
        result = self._send("tools/call", {
            "name": name,
            "arguments": arguments,
        })

        # Extract tool result from MCP content wrapper
        content = result.get("result", {}).get("content", [])
        if content:
            text = content[0].get("text", "{}")
            return json.loads(text)

        error = result.get("error", {})
        raise MCPTransportError(
            error.get("message", "Empty tool response")
        )

    def health_check(self) -> dict:
        """GET /health on the MCP server (non-MCP endpoint)."""
        try:
            resp = self._session.get(
                f"{self.base_url}/health", timeout=5
            )
            if resp.status_code == 200:
                return resp.json()
            return {"status": "error", "http_code": resp.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e)}


# Module-level singleton
_transport: Optional[MCPTransport] = None


def get_mcp_transport() -> MCPTransport:
    """Get or create the shared MCP transport instance."""
    global _transport
    if _transport is None:
        _transport = MCPTransport()
    return _transport
