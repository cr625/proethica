"""
Script to check entity parent classes.
This will help debug issues with parent class selection in the entity editor.
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.services.ontology_entity_service import OntologyEntityService

def check_entity_parents(ontology_id=1):
    """Check parent classes for entities in the given ontology."""
    print(f"Checking entities for ontology ID {ontology_id}...")
    
    # Get the entity service instance
    entity_service = OntologyEntityService.get_instance()
    
    # Create a dummy world object
    class DummyWorld:
        def __init__(self, ontology_id):
            self.ontology_id = ontology_id
    
    dummy_world = DummyWorld(ontology_id)
    
    # Get entities
    entities = entity_service.get_entities_for_world(dummy_world)
    
    # Check roles
    print("\nROLES:")
    for role in entities['entities']['roles']:
        print(f"Label: {role['label']}")
        print(f"  ID: {role['id']}")
        print(f"  Parent class: {role.get('parent_class')}")
        print()
    
    # Check conditions
    print("\nCONDITIONS:")
    for condition in entities['entities']['conditions']:
        print(f"Label: {condition['label']}")
        print(f"  ID: {condition['id']}")
        print(f"  Parent class: {condition.get('parent_class')}")
        print()
    
    # Check other entity types (resources, actions, events, capabilities)
    for entity_type in ['resources', 'actions', 'events', 'capabilities']:
        print(f"\n{entity_type.upper()}:")
        for entity in entities['entities'][entity_type]:
            print(f"Label: {entity['label']}")
            print(f"  ID: {entity['id']}")
            print(f"  Parent class: {entity.get('parent_class')}")
            print()

if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        # Check for ontology ID from command line
        ontology_id = 1
        if len(sys.argv) > 1:
            try:
                ontology_id = int(sys.argv[1])
            except ValueError:
                print(f"Invalid ontology ID: {sys.argv[1]}")
                sys.exit(1)
        
        check_entity_parents(ontology_id)
