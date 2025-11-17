"""
STUB: Entity Service
This is a placeholder service to maintain backward compatibility.
Entity creation/modification functionality has moved to OntServe.

Previously located at: ontology_editor.services.entity_service
"""

import logging
from typing import Tuple, Dict, Any, List

logger = logging.getLogger(__name__)


class EntityService:
    """Stub implementation of EntityService for backward compatibility."""

    @staticmethod
    def create_entity(
        ontology_id: int,
        entity_type: str,
        label: str,
        description: str = "",
        parent_class_uri: str = None,
        properties: Dict[str, Any] = None,
        commit_message: str = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Stub method for creating entities in ontology.

        This functionality has moved to OntServe. To create entities:
        1. Use OntServe web interface (http://localhost:5003/editor)
        2. Use OntServe MCP API (http://localhost:8082) if write tools are available

        Args:
            ontology_id: ID of ontology
            entity_type: Type of entity (role, principle, etc.)
            label: Entity label
            description: Entity description
            parent_class_uri: Parent class URI
            properties: Additional properties
            commit_message: Commit message

        Returns:
            (False, error_dict) - This stub always returns failure
        """
        logger.warning(
            f"EntityService.create_entity called for '{label}' but functionality "
            f"has moved to OntServe. Use OntServe web interface or API instead."
        )

        return (False, {
            'error': 'EntityService is a stub. Entity creation has moved to OntServe.',
            'message': 'Please use OntServe web interface at http://localhost:5003/editor',
            'entity_label': label,
            'entity_type': entity_type
        })

    @staticmethod
    def get_entities(
        ontology_id: int,
        entity_type: str = None
    ) -> List[Dict[str, Any]]:
        """
        Stub method for getting entities from ontology.

        This functionality has moved to OntServe. To get entities:
        - Use OntServeAnnotationService.get_ontology_concepts()
        - Use ExternalMCPClient.get_entities_by_category()

        Args:
            ontology_id: ID of ontology
            entity_type: Optional type filter

        Returns:
            Empty list - Use OntServe services instead
        """
        logger.warning(
            f"EntityService.get_entities called but functionality has moved to OntServe. "
            f"Use OntServeAnnotationService or ExternalMCPClient instead."
        )

        return []

    @staticmethod
    def update_entity(
        entity_uri: str,
        updates: Dict[str, Any],
        commit_message: str = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Stub method for updating entities."""
        logger.warning(
            f"EntityService.update_entity called for '{entity_uri}' but functionality "
            f"has moved to OntServe."
        )

        return (False, {
            'error': 'EntityService is a stub. Entity updates have moved to OntServe.',
            'message': 'Please use OntServe web interface at http://localhost:5003/editor'
        })

    @staticmethod
    def delete_entity(
        entity_uri: str,
        commit_message: str = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Stub method for deleting entities."""
        logger.warning(
            f"EntityService.delete_entity called for '{entity_uri}' but functionality "
            f"has moved to OntServe."
        )

        return (False, {
            'error': 'EntityService is a stub. Entity deletion has moved to OntServe.',
            'message': 'Please use OntServe web interface at http://localhost:5003/editor'
        })
