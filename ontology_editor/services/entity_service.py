"""
STUB: Entity Service
This is a placeholder service to maintain backward compatibility.
Ontology entity management functionality has moved to OntServe.
"""

class EntityService:
    """Stub implementation of EntityService."""
    
    def __init__(self, ontology_name=None):
        """Initialize stub EntityService."""
        self.ontology_name = ontology_name
    
    def create_entity(self, entity_data):
        """
        Stub method for creating entities.
        
        Args:
            entity_data: Dictionary containing entity information
            
        Returns:
            dict: Success response indicating migration needed
        """
        return {
            'success': False,
            'message': 'Entity creation has moved to OntServe. Visit http://localhost:5003',
            'migration_required': True
        }
    
    def update_entity(self, entity_uri, entity_data):
        """Stub method for updating entities."""
        return {
            'success': False,
            'message': 'Entity updates have moved to OntServe. Visit http://localhost:5003',
            'migration_required': True
        }
    
    def delete_entity(self, entity_uri):
        """Stub method for deleting entities."""
        return {
            'success': False,
            'message': 'Entity deletion has moved to OntServe. Visit http://localhost:5003',
            'migration_required': True
        }
    
    def get_entity(self, entity_uri):
        """Stub method for getting entity by URI."""
        return None
    
    def search_entities(self, query, entity_type=None):
        """Stub method for searching entities."""
        return []
    
    def validate_entity(self, entity_data):
        """Stub method for entity validation."""
        return {'valid': False, 'message': 'Validation moved to OntServe'}