"""
Legacy MCP Client compatibility shim.

The original MCPClient called REST endpoints on OntServe that never existed.
All ontology calls silently fell back to mock data. This slim replacement
preserves the same public API (21 consumer files import it) while removing
600+ lines of dead REST/mock code.

Active MCP communication uses ExternalMCPClient and OntServeMCPClient,
which speak the correct MCP Streamable HTTP protocol (JSON-RPC over SSE).
"""

import logging
from typing import Dict, List, Any, Optional

from app.services.zotero_client import ZoteroClient

logger = logging.getLogger(__name__)


class MCPClient:
    """Compatibility shim -- ontology methods return empty data,
    Zotero methods delegate to ZoteroClient."""

    _instance = None

    @classmethod
    def get_instance(cls) -> 'MCPClient':
        if cls._instance is None:
            cls._instance = MCPClient()
        return cls._instance

    def __init__(self):
        self.is_connected = False
        self._zotero_client = None

    # -- Ontology stubs (always returned empty/mock data anyway) -----------

    def get_world_entities(self, ontology_source: str, entity_type: str = "all") -> Dict[str, Any]:
        return {"entities": {}, "is_mock": True}

    def get_ontology_entities(self, ontology_source: str, entity_type: str = "all") -> Dict[str, Any]:
        return self.get_world_entities(ontology_source, entity_type)

    def get_guidelines(self, world_name: str) -> Dict[str, Any]:
        return {}

    def get_ontology_status(self, ontology_source: str) -> Dict[str, Any]:
        return {'status': 'unknown', 'message': 'Legacy MCP client -- use ExternalMCPClient'}

    def get_ontology_content(self, ontology_source: str) -> Dict[str, Any]:
        return {'content': '', 'success': False, 'error': 'Legacy MCP client removed'}

    def get_mock_entities(self, ontology_source: str) -> Dict[str, Any]:
        return {"entities": {}}

    def get_mock_guidelines(self, world_name: str) -> Dict[str, Any]:
        return {}

    def refresh_world_entities(self, world_id: int) -> bool:
        return False

    def refresh_world_entities_by_ontology(self, ontology_source: str) -> Dict[str, Any]:
        return {'success': False, 'message': 'Legacy MCP client removed'}

    def check_connection(self) -> bool:
        return False

    # -- Zotero pass-throughs (delegate to ZoteroClient) -------------------

    def _zotero(self) -> ZoteroClient:
        if self._zotero_client is None:
            self._zotero_client = ZoteroClient.get_instance()
        return self._zotero_client

    def search_zotero_items(self, query: str, collection_key: Optional[str] = None,
                            limit: int = 20) -> List[Dict[str, Any]]:
        try:
            return self._zotero().search_items(query, collection_key, limit)
        except Exception as e:
            logger.error(f"Error searching Zotero items: {e}")
            return []

    def get_zotero_citation(self, item_key: str, style: str = "apa") -> str:
        try:
            return self._zotero().get_citation(item_key, style)
        except Exception as e:
            logger.error(f"Error getting citation: {e}")
            return f"Error: {e}"

    def get_zotero_bibliography(self, item_keys: List[str], style: str = "apa") -> str:
        try:
            return self._zotero().get_bibliography(item_keys, style)
        except Exception as e:
            logger.error(f"Error getting bibliography: {e}")
            return f"Error: {e}"

    def get_zotero_collections(self) -> List[Dict[str, Any]]:
        try:
            return self._zotero().get_collections()
        except Exception as e:
            logger.error(f"Error getting collections: {e}")
            return []

    def get_zotero_recent_items(self, limit: int = 20) -> List[Dict[str, Any]]:
        try:
            return self._zotero().get_recent_items(limit)
        except Exception as e:
            logger.error(f"Error getting recent items: {e}")
            return []

    def add_zotero_item(self, item_type: str, title: str,
                        creators: Optional[List[Dict[str, str]]] = None,
                        collection_key: Optional[str] = None,
                        additional_fields: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        try:
            return self._zotero().add_item(item_type, title, creators, collection_key, additional_fields)
        except Exception as e:
            logger.error(f"Error adding item: {e}")
            return {"error": str(e)}

    def get_references_for_world(self, world) -> List[Dict[str, Any]]:
        try:
            query_parts = []
            for attr in ('name', 'description', 'ontology_source'):
                val = getattr(world, attr, None)
                if val:
                    query_parts.append(val)
            return self._zotero().search_items(" ".join(query_parts)) if query_parts else []
        except Exception as e:
            logger.error(f"Error retrieving references: {e}")
            return []

    def get_references_for_scenario(self, scenario) -> List[Dict[str, Any]]:
        try:
            query_parts = []
            for attr in ('name', 'description'):
                val = getattr(scenario, attr, None)
                if val:
                    query_parts.append(val)
            return self._zotero().search_items(" ".join(query_parts)) if query_parts else []
        except Exception as e:
            logger.error(f"Error retrieving references for scenario: {e}")
            return []
