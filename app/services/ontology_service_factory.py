"""
Stub Ontology Service Factory - ARCHIVED functionality moved to OntServe.

This stub exists to prevent import errors during the transition period.
Real ontology services now operate through OntServe MCP integration.
"""

import logging

logger = logging.getLogger(__name__)

class OntologyServiceStub:
    """
    STUB SERVICE - Original functionality moved to OntServe
    
    This provides basic method stubs to prevent errors during transition.
    For actual ontology operations, use OntServe MCP integration.
    """
    
    def get_entities_for_world(self, world_id, entity_type=None):
        """STUB: Returns empty list with migration message."""
        logger.warning(f"get_entities_for_world called for world {world_id} - functionality moved to OntServe MCP")
        return []
    
    def get_concepts_by_type(self, world_id, concept_type):
        """STUB: Returns empty list with migration message.""" 
        logger.warning(f"get_concepts_by_type called for {concept_type} - functionality moved to OntServe MCP")
        return []
    
    def search_entities(self, query, world_id=None):
        """STUB: Returns empty list with migration message."""
        logger.warning(f"search_entities called - functionality moved to OntServe MCP")
        return []
    
    def get_ontology_stats(self, world_id):
        """STUB: Returns zero stats with migration message."""
        return {
            'entities': 0,
            'classes': 0, 
            'properties': 0,
            'message': 'Ontology stats moved to OntServe. Use MCP integration or visit http://localhost:5003'
        }

def get_ontology_service():
    """
    Factory function that returns the stub service.
    
    Returns:
        OntologyServiceStub: Stub service with migration messages
    """
    return OntologyServiceStub()

# Maintain backward compatibility
def create_ontology_service(service_type='stub'):
    """Legacy factory function for backward compatibility."""
    logger.warning(f"create_ontology_service called - functionality moved to OntServe MCP")
    return get_ontology_service()