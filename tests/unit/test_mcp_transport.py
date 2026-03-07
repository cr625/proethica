"""
Unit tests for MCPTransport (ProEthica -> OntServe MCP client).

Tests SSE parsing, session management, error handling, and tool call
result extraction. All HTTP responses are mocked -- no live server needed.
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from app.services.mcp_transport import MCPTransport, MCPTransportError


@pytest.fixture
def transport():
    """Create transport without hitting a real server."""
    with patch.object(MCPTransport, '_send'):
        t = MCPTransport.__new__(MCPTransport)
        t.base_url = "http://localhost:8082"
        t.mcp_endpoint = "http://localhost:8082/mcp"
        t.timeout = 30
        t._session = MagicMock()
        t._session_id = None
        t._request_id = 0
        t._initialized = False
    return t


class TestSSEParsing:
    """Test SSE response parsing."""

    def test_parse_single_data_line(self):
        payload = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
        sse_text = f"data: {json.dumps(payload)}\n\n"
        result = MCPTransport._parse_sse(sse_text)
        assert result == payload

    def test_parse_sse_with_event_lines(self):
        payload = {"jsonrpc": "2.0", "id": 1, "result": {}}
        sse_text = f"event: message\ndata: {json.dumps(payload)}\n\n"
        result = MCPTransport._parse_sse(sse_text)
        assert result == payload

    def test_parse_sse_ignores_comments(self):
        payload = {"jsonrpc": "2.0", "id": 1, "result": {}}
        sse_text = f": keepalive\ndata: {json.dumps(payload)}\n\n"
        result = MCPTransport._parse_sse(sse_text)
        assert result == payload

    def test_parse_sse_no_data_raises(self):
        with pytest.raises(MCPTransportError, match="No data line"):
            MCPTransport._parse_sse("event: message\n\n")

    def test_parse_sse_empty_raises(self):
        with pytest.raises(MCPTransportError, match="No data line"):
            MCPTransport._parse_sse("")


class TestRequestIdCounter:
    """Test request ID incrementing."""

    def test_increments(self, transport):
        assert transport._next_id() == 1
        assert transport._next_id() == 2
        assert transport._next_id() == 3


class TestSend:
    """Test the _send method HTTP handling."""

    def test_plain_json_response(self, transport):
        response = MagicMock()
        response.status_code = 200
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}
        transport._session.post.return_value = response

        result = MCPTransport._send(transport, "tools/list", {})
        assert result == {"jsonrpc": "2.0", "id": 1, "result": {"ok": True}}

    def test_sse_response(self, transport):
        payload = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
        response = MagicMock()
        response.status_code = 200
        response.headers = {
            "content-type": "text/event-stream",
            "Mcp-Session-Id": "sess-123",
        }
        response.text = f"data: {json.dumps(payload)}\n\n"
        transport._session.post.return_value = response

        result = MCPTransport._send(transport, "tools/list", {})
        assert result == payload
        assert transport._session_id == "sess-123"

    def test_session_id_sent_in_headers(self, transport):
        transport._session_id = "sess-abc"
        response = MagicMock()
        response.status_code = 200
        response.headers = {"content-type": "application/json"}
        response.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": {}}
        transport._session.post.return_value = response

        MCPTransport._send(transport, "tools/list", {})

        call_kwargs = transport._session.post.call_args
        assert call_kwargs.kwargs["headers"]["Mcp-Session-Id"] == "sess-abc"

    def test_non_200_raises(self, transport):
        response = MagicMock()
        response.status_code = 500
        response.headers = {}
        transport._session.post.return_value = response

        with pytest.raises(MCPTransportError, match="HTTP 500"):
            MCPTransport._send(transport, "tools/list", {})


class TestInitialize:
    """Test MCP initialize handshake."""

    def test_initialize_sets_flag(self, transport):
        init_result = {
            "jsonrpc": "2.0", "id": 1,
            "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "OntServe", "version": "3.1.0"},
                "capabilities": {},
            }
        }
        with patch.object(transport, '_send', return_value=init_result):
            result = transport.initialize()
            assert transport._initialized is True
            assert result["result"]["protocolVersion"] == "2024-11-05"

    def test_initialize_failure_does_not_set_flag(self, transport):
        error_result = {"jsonrpc": "2.0", "id": 1, "error": {"code": -1, "message": "fail"}}
        with patch.object(transport, '_send', return_value=error_result):
            transport.initialize()
            assert transport._initialized is False


class TestListTools:
    """Test tools/list."""

    def test_returns_tool_list(self, transport):
        tools = [
            {"name": "get_entity_by_label", "inputSchema": {"type": "object", "properties": {}}},
            {"name": "get_domain_info", "inputSchema": {"type": "object", "properties": {}}},
        ]
        transport._initialized = True
        with patch.object(transport, '_send', return_value={"result": {"tools": tools}}):
            result = transport.list_tools()
            assert len(result) == 2
            assert result[0]["name"] == "get_entity_by_label"

    def test_auto_initializes(self, transport):
        init_result = {"result": {"protocolVersion": "2024-11-05", "capabilities": {}}}
        list_result = {"result": {"tools": []}}

        call_count = 0
        def fake_send(method, params=None):
            nonlocal call_count
            call_count += 1
            if method == "initialize":
                transport._initialized = True
                return init_result
            return list_result

        with patch.object(transport, '_send', side_effect=fake_send):
            transport.list_tools()
            assert call_count == 2  # initialize + list


class TestCallTool:
    """Test tools/call and result extraction."""

    def test_extracts_text_content(self, transport):
        transport._initialized = True
        tool_payload = {"entities": [{"label": "Engineer"}], "total_count": 1}
        mcp_result = {
            "result": {
                "content": [{"type": "text", "text": json.dumps(tool_payload)}]
            }
        }
        with patch.object(transport, '_send', return_value=mcp_result):
            result = transport.call_tool("get_entities_by_category", {"category": "Role"})
            assert result["total_count"] == 1
            assert result["entities"][0]["label"] == "Engineer"

    def test_empty_content_raises(self, transport):
        transport._initialized = True
        mcp_result = {"result": {"content": []}}
        with patch.object(transport, '_send', return_value=mcp_result):
            with pytest.raises(MCPTransportError, match="Empty tool response"):
                transport.call_tool("get_domain_info", {"domain_id": "x"})

    def test_error_response_raises(self, transport):
        transport._initialized = True
        mcp_result = {"error": {"code": -32600, "message": "Invalid request"}}
        with patch.object(transport, '_send', return_value=mcp_result):
            with pytest.raises(MCPTransportError, match="Invalid request"):
                transport.call_tool("bad_tool", {})


class TestHealthCheck:
    """Test non-MCP health endpoint."""

    def test_healthy(self, transport):
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"status": "ok"}
        transport._session.get.return_value = response

        result = transport.health_check()
        assert result["status"] == "ok"

    def test_connection_error(self, transport):
        transport._session.get.side_effect = ConnectionError("refused")
        result = transport.health_check()
        assert result["status"] == "error"

    def test_non_200(self, transport):
        response = MagicMock()
        response.status_code = 503
        transport._session.get.return_value = response

        result = transport.health_check()
        assert result["status"] == "error"
        assert result["http_code"] == 503


class TestGetMCPTransport:
    """Test module-level singleton."""

    def test_returns_same_instance(self):
        import app.services.mcp_transport as mod
        mod._transport = None
        with patch.object(MCPTransport, '__init__', return_value=None):
            t1 = mod.get_mcp_transport()
            t2 = mod.get_mcp_transport()
            assert t1 is t2
        mod._transport = None  # cleanup
