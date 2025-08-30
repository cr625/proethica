"""
STUB: Ontology Triple Loader
This is a placeholder service to maintain backward compatibility.
Ontology triple loading functionality has moved to OntServe.
"""

class OntologyTripleLoader:
    """Stub implementation of OntologyTripleLoader."""
    
    def __init__(self, ontology_name=None):
        """Initialize stub triple loader."""
        self.ontology_name = ontology_name
    
    def load_triples(self):
        """
        Stub method for loading triples.
        
        Returns:
            list: Empty list (triple loading moved to OntServe)
        """
        return []
    
    def get_entities_by_type(self, entity_type):
        """Stub method for getting entities by type."""
        return []
    
    def get_entity_triples(self, entity_uri):
        """Stub method for getting entity triples."""
        return []
    
    def refresh_ontology(self):
        """Stub method for refreshing ontology."""
        return {
            'success': False,
            'message': 'Ontology refresh has moved to OntServe. Visit http://localhost:5003'
        }