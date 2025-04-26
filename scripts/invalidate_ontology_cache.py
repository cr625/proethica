"""
Script to invalidate the ontology entity cache.
This will force a re-extraction of entities with the updated code
that now includes parent class information.
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.services.ontology_entity_service import OntologyEntityService
from app.models.ontology import Ontology

def invalidate_entity_cache():
    """Invalidate the entity cache for all ontologies."""
    print("Invalidating ontology entity cache...")
    
    # Get the entity service instance
    entity_service = OntologyEntityService.get_instance()
    
    # Get all ontologies
    ontologies = Ontology.query.all()
    print(f"Found {len(ontologies)} ontologies")
    
    # Invalidate cache for each ontology
    for ontology in ontologies:
        print(f"Invalidating cache for ontology {ontology.id}: {ontology.name}")
        entity_service.invalidate_cache(ontology.id)
    
    # Also invalidate the global cache
    entity_service.invalidate_cache()
    
    print("Done. Entity cache has been invalidated.")

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        invalidate_entity_cache()
