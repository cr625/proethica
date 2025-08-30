"""
STUB: Engineering Ontology Service
This is a placeholder service to maintain backward compatibility.
Engineering ontology functionality has moved to OntServe.
"""

class EngineeringOntologyService:
    """Stub implementation of EngineeringOntologyService."""
    
    def get_concepts(self, concept_type=None):
        """
        Stub method for getting concepts.
        
        Args:
            concept_type: Optional filter by concept type
            
        Returns:
            list: Empty list (concepts now come from OntServe)
        """
        return []
    
    def get_concept_by_uri(self, uri):
        """Stub method for getting concept by URI."""
        return None
    
    def search_concepts(self, query, concept_type=None):
        """Stub method for searching concepts."""
        return []
    
    def get_related_concepts(self, concept_uri):
        """Stub method for getting related concepts."""
        return []
    
    def get_concept_hierarchy(self, concept_type=None):
        """Stub method for getting concept hierarchy."""
        return {}

# Create singleton instance for compatibility
engineering_ontology_service = EngineeringOntologyService()