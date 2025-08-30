"""
STUB: Ontology Entity Service
This is a placeholder service to maintain backward compatibility.
Ontology functionality has moved to OntServe.
"""

class OntologyEntityService:
    """Stub implementation of OntologyEntityService."""
    
    _instance = None
    
    @classmethod
    def get_instance(cls):
        """Get singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def get_entities_for_world(self, world):
        """
        Stub method that returns empty results.
        
        Args:
            world: World object
            
        Returns:
            list: Empty list (entities would come from OntServe now)
        """
        # Return empty list - this functionality has moved to OntServe
        # In the future, this would query OntServe via MCP
        return []
    
    def get_entity_by_uri(self, uri):
        """Stub method for getting entity by URI."""
        return None
    
    def search_entities(self, query, entity_type=None):
        """Stub method for searching entities."""
        return []
    
    def get_entity_relationships(self, entity_uri):
        """Stub method for getting entity relationships."""
        return []