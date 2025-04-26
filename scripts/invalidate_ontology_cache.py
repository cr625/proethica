"""
Script to invalidate the ontology cache, forcing the system to reload ontology data
from the database. This should be run after making changes to the ontology structure
that need to be immediately reflected in the UI.
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.services.ontology_entity_service import OntologyEntityService

def invalidate_cache(ontology_id=None):
    """
    Invalidate the ontology cache, either for a specific ontology or for all ontologies.
    
    Args:
        ontology_id (int, optional): Specific ontology ID to invalidate, or None for all ontologies.
    """
    print("Invalidating ontology cache...")
    
    app = create_app()
    with app.app_context():
        # Create an instance of the OntologyEntityService
        service = OntologyEntityService()
        
        if ontology_id:
            # Invalidate specific ontology cache
            print(f"Invalidating cache for ontology ID {ontology_id}")
            service.invalidate_cache(ontology_id)
            print(f"Cache invalidated for ontology ID {ontology_id}")
        else:
            # Invalidate all ontology caches
            print("Invalidating cache for all ontologies")
            service.invalidate_cache()
            print("All ontology caches invalidated")
        
        print("\nCache invalidation complete. The system will reload ontology data from the database on next access.")

if __name__ == "__main__":
    # Parse command line arguments
    if len(sys.argv) > 1:
        try:
            ontology_id = int(sys.argv[1])
            invalidate_cache(ontology_id)
        except ValueError:
            print(f"Invalid ontology ID: {sys.argv[1]}")
            print("Usage: python invalidate_ontology_cache.py [ontology_id]")
            sys.exit(1)
    else:
        # No arguments, invalidate all caches
        invalidate_cache()
