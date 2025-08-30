"""
STUB: Ontology Term Recognition Service
This is a placeholder service to maintain backward compatibility.
Ontology term recognition functionality has moved to OntServe.
"""

class OntologyTermRecognitionService:
    """Stub implementation of OntologyTermRecognitionService."""
    
    def __init__(self):
        """Initialize stub term recognition service."""
        pass
    
    def recognize_terms(self, text, ontology_name=None):
        """
        Stub method for recognizing ontology terms in text.
        
        Args:
            text: Text to analyze
            ontology_name: Optional ontology to search in
            
        Returns:
            list: Empty list (term recognition moved to OntServe)
        """
        return []
    
    def get_term_definitions(self, terms):
        """
        Stub method for getting term definitions.
        
        Args:
            terms: List of terms to get definitions for
            
        Returns:
            dict: Empty dictionary (definitions moved to OntServe)
        """
        return {}
    
    def find_similar_terms(self, term, threshold=0.8):
        """
        Stub method for finding similar terms.
        
        Args:
            term: Term to find similarities for
            threshold: Similarity threshold
            
        Returns:
            list: Empty list (similarity search moved to OntServe)
        """
        return []

# Create singleton instance for compatibility
ontology_term_recognition_service = OntologyTermRecognitionService()