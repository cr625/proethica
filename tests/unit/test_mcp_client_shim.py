"""
Unit tests for the MCPClient compatibility shim.

The legacy MCPClient was rewritten from 727 lines to a slim shim that:
- Returns empty data for ontology methods (previously returned mock/empty data anyway)
- Delegates Zotero methods to ZoteroClient
- Preserves get_instance() singleton pattern used by 21 consumer files
"""

import pytest
from unittest.mock import patch, MagicMock


class TestMCPClientSingleton:
    """Test singleton pattern preserved for consumers."""

    def test_get_instance_returns_same_object(self):
        from app.services.mcp_client import MCPClient
        MCPClient._instance = None
        try:
            a = MCPClient.get_instance()
            b = MCPClient.get_instance()
            assert a is b
        finally:
            MCPClient._instance = None

    def test_is_connected_false(self):
        from app.services.mcp_client import MCPClient
        MCPClient._instance = None
        try:
            client = MCPClient.get_instance()
            assert client.is_connected is False
        finally:
            MCPClient._instance = None

    def test_check_connection_returns_false(self):
        from app.services.mcp_client import MCPClient
        MCPClient._instance = None
        try:
            client = MCPClient.get_instance()
            assert client.check_connection() is False
        finally:
            MCPClient._instance = None


class TestOntologyStubs:
    """Test that ontology methods return empty data (same behavior as before)."""

    @pytest.fixture
    def client(self):
        from app.services.mcp_client import MCPClient
        MCPClient._instance = None
        c = MCPClient.get_instance()
        yield c
        MCPClient._instance = None

    def test_get_world_entities_returns_empty(self, client):
        result = client.get_world_entities("engineering_ethics.ttl")
        assert result == {"entities": {}, "is_mock": True}

    def test_get_world_entities_with_entity_type(self, client):
        result = client.get_world_entities("engineering_ethics.ttl", entity_type="roles")
        assert result == {"entities": {}, "is_mock": True}

    def test_get_ontology_entities_delegates(self, client):
        result = client.get_ontology_entities("engineering_ethics.ttl", "roles")
        assert result == {"entities": {}, "is_mock": True}

    def test_get_guidelines_returns_empty(self, client):
        result = client.get_guidelines("engineering")
        assert result == {}

    def test_get_ontology_status_returns_unknown(self, client):
        result = client.get_ontology_status("engineering-ethics")
        assert result['status'] == 'unknown'

    def test_get_ontology_content_returns_failure(self, client):
        result = client.get_ontology_content("engineering_ethics.ttl")
        assert result['success'] is False

    def test_get_mock_entities_returns_empty(self, client):
        result = client.get_mock_entities("engineering_ethics.ttl")
        assert result == {"entities": {}}

    def test_get_mock_guidelines_returns_empty(self, client):
        """This method didn't exist in the old MCPClient (latent AttributeError).
        Now it exists and returns empty data."""
        result = client.get_mock_guidelines("engineering")
        assert result == {}

    def test_refresh_world_entities_returns_false(self, client):
        result = client.refresh_world_entities(1)
        assert result is False

    def test_refresh_world_entities_by_ontology_returns_failure(self, client):
        result = client.refresh_world_entities_by_ontology("engineering-ethics")
        assert result['success'] is False


class TestZoteroDelegation:
    """Test that Zotero methods delegate to ZoteroClient."""

    @pytest.fixture
    def client_with_mock_zotero(self):
        from app.services.mcp_client import MCPClient
        MCPClient._instance = None
        c = MCPClient.get_instance()
        mock_zotero = MagicMock()
        c._zotero_client = mock_zotero
        yield c, mock_zotero
        MCPClient._instance = None

    def test_search_zotero_items(self, client_with_mock_zotero):
        client, mock_z = client_with_mock_zotero
        mock_z.search_items.return_value = [{'key': 'abc'}]
        result = client.search_zotero_items("ethics", limit=5)
        assert result == [{'key': 'abc'}]
        mock_z.search_items.assert_called_once_with("ethics", None, 5)

    def test_search_zotero_items_with_collection(self, client_with_mock_zotero):
        client, mock_z = client_with_mock_zotero
        mock_z.search_items.return_value = []
        client.search_zotero_items("ethics", collection_key="COL1", limit=10)
        mock_z.search_items.assert_called_once_with("ethics", "COL1", 10)

    def test_get_zotero_citation(self, client_with_mock_zotero):
        client, mock_z = client_with_mock_zotero
        mock_z.get_citation.return_value = "Doe (2024)"
        result = client.get_zotero_citation("item1", "apa")
        assert result == "Doe (2024)"
        mock_z.get_citation.assert_called_once_with("item1", "apa")

    def test_get_zotero_bibliography(self, client_with_mock_zotero):
        client, mock_z = client_with_mock_zotero
        mock_z.get_bibliography.return_value = "Bibliography text"
        result = client.get_zotero_bibliography(["a", "b"], "chicago")
        assert result == "Bibliography text"
        mock_z.get_bibliography.assert_called_once_with(["a", "b"], "chicago")

    def test_get_zotero_collections(self, client_with_mock_zotero):
        client, mock_z = client_with_mock_zotero
        mock_z.get_collections.return_value = [{'name': 'Ethics'}]
        result = client.get_zotero_collections()
        assert result == [{'name': 'Ethics'}]

    def test_get_zotero_recent_items(self, client_with_mock_zotero):
        client, mock_z = client_with_mock_zotero
        mock_z.get_recent_items.return_value = [{'key': 'recent1'}]
        result = client.get_zotero_recent_items(limit=10)
        assert result == [{'key': 'recent1'}]
        mock_z.get_recent_items.assert_called_once_with(10)

    def test_add_zotero_item(self, client_with_mock_zotero):
        client, mock_z = client_with_mock_zotero
        mock_z.add_item.return_value = {"success": True}
        result = client.add_zotero_item("journalArticle", "Test Title")
        assert result == {"success": True}
        mock_z.add_item.assert_called_once_with(
            "journalArticle", "Test Title", None, None, None
        )

    def test_get_references_for_world(self, client_with_mock_zotero):
        client, mock_z = client_with_mock_zotero
        mock_z.search_items.return_value = [{'key': 'ref1'}]

        world = MagicMock()
        world.name = "Engineering Ethics"
        world.description = "Test world"
        world.ontology_source = "eng_ethics.ttl"

        result = client.get_references_for_world(world)
        assert result == [{'key': 'ref1'}]
        mock_z.search_items.assert_called_once()
        call_args = mock_z.search_items.call_args[0][0]
        assert "Engineering Ethics" in call_args
        assert "Test world" in call_args

    def test_get_references_for_scenario(self, client_with_mock_zotero):
        client, mock_z = client_with_mock_zotero
        mock_z.search_items.return_value = []

        scenario = MagicMock()
        scenario.name = "Bridge Design"
        scenario.description = "Safety scenario"

        result = client.get_references_for_scenario(scenario)
        assert result == []
        call_args = mock_z.search_items.call_args[0][0]
        assert "Bridge Design" in call_args

    def test_get_references_for_world_no_attributes(self, client_with_mock_zotero):
        client, mock_z = client_with_mock_zotero
        world = MagicMock(spec=[])  # no attributes
        result = client.get_references_for_world(world)
        assert result == []
        mock_z.search_items.assert_not_called()


class TestZoteroErrorHandling:
    """Test that Zotero method errors are caught and return safe defaults."""

    @pytest.fixture
    def client_with_failing_zotero(self):
        from app.services.mcp_client import MCPClient
        MCPClient._instance = None
        c = MCPClient.get_instance()
        mock_zotero = MagicMock()
        mock_zotero.search_items.side_effect = Exception("Connection refused")
        mock_zotero.get_citation.side_effect = Exception("Connection refused")
        mock_zotero.get_bibliography.side_effect = Exception("Connection refused")
        mock_zotero.get_collections.side_effect = Exception("Connection refused")
        mock_zotero.get_recent_items.side_effect = Exception("Connection refused")
        mock_zotero.add_item.side_effect = Exception("Connection refused")
        c._zotero_client = mock_zotero
        yield c
        MCPClient._instance = None

    def test_search_error_returns_empty_list(self, client_with_failing_zotero):
        result = client_with_failing_zotero.search_zotero_items("test")
        assert result == []

    def test_citation_error_returns_error_string(self, client_with_failing_zotero):
        result = client_with_failing_zotero.get_zotero_citation("key1")
        assert "Error" in result

    def test_bibliography_error_returns_error_string(self, client_with_failing_zotero):
        result = client_with_failing_zotero.get_zotero_bibliography(["k1"])
        assert "Error" in result

    def test_collections_error_returns_empty_list(self, client_with_failing_zotero):
        result = client_with_failing_zotero.get_zotero_collections()
        assert result == []

    def test_recent_items_error_returns_empty_list(self, client_with_failing_zotero):
        result = client_with_failing_zotero.get_zotero_recent_items()
        assert result == []

    def test_add_item_error_returns_error_dict(self, client_with_failing_zotero):
        result = client_with_failing_zotero.add_zotero_item("book", "Title")
        assert "error" in result
