import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import render_template, request
from app import create_app
from ontology_editor import create_ontology_editor_blueprint

def add_debug_route():
    """Add debug route to ontology editor blueprint."""
    app = create_app()
    
    # Create a new blueprint with a different name and URL prefix
    editor_bp = create_ontology_editor_blueprint(
        config=None, 
        url_prefix='/ontology-editor-debug'
    )
    
    @editor_bp.route('/debug')
    def debug_entity_editor():
        """Debug version of entity editor view."""
        ontology_id = request.args.get('ontology_id')
        view = request.args.get('view', 'full')
        world_id = request.args.get('world_id')
        
        # Similar to the entity_editor function but using debug template
        from app.models.ontology import Ontology
        from app.models.ontology_version import OntologyVersion
        from ontology_editor.services.entity_service import EntityService
        
        # Get the ontology
        ontology = Ontology.query.get_or_404(ontology_id)
        
        # Get the latest version
        latest_version = OntologyVersion.query.filter_by(
            ontology_id=ontology_id
        ).order_by(
            OntologyVersion.version_number.desc()
        ).first()
        
        # Get entities
        from app.services.ontology_entity_service import OntologyEntityService
        entity_service = OntologyEntityService.get_instance()
        
        # Create a world-like object with the required ontology_id field
        class DummyWorld:
            def __init__(self, ontology_id):
                self.ontology_id = ontology_id
                
        dummy_world = DummyWorld(ontology_id)
        entities = entity_service.get_entities_for_world(dummy_world)
        
        # Add debug info for each role
        print("ENTITIES LOADED FOR DEBUG:")
        for role in entities['entities']['roles']:
            print(f"Role: {role['label']}")
            print(f"  ID: {role['id']}")
            print(f"  Parent class: {role.get('parent_class')}")
        
        # Get parent classes for each entity type
        parent_classes = {}
        for entity_type in ['role', 'condition', 'resource', 'action', 'event', 'capability']:
            parent_classes[entity_type] = EntityService.get_valid_parents(ontology_id, entity_type)
            
        # Get all capabilities for roles
        capabilities = []
        if 'entities' in entities and 'capabilities' in entities['entities']:
            capabilities = entities['entities']['capabilities']
        
        # Serialize parent classes and capabilities for JavaScript
        serialized_parents = {}
        for entity_type, parents in parent_classes.items():
            serialized_parents[entity_type] = parents
            
        serialized_capabilities = capabilities
        
        # Helper functions
        def is_editable(entity):
            return EntityService.is_editable(entity)
            
        def get_entity_origin(entity):
            return EntityService.get_entity_origin(entity)
            
        def is_parent_of(parent, entity):
            if not entity or not parent:
                return False
            print(f"Checking if {parent.get('id')} is parent of {entity.get('label')}")
            print(f"  Parent ID: {parent.get('id')}")
            print(f"  Entity parent_class: {entity.get('parent_class')}")
            print(f"  Match: {parent.get('id') == entity.get('parent_class')}")
            
            # Check if parent.id is in entity's parents
            if 'parent_class' in entity:
                return parent.get('id') == entity.get('parent_class')
            
            return False
            
        def get_valid_parents(entity_type):
            return parent_classes.get(entity_type, [])
            
        def has_capability(role, capability):
            if not role or not capability or not role.get('capabilities'):
                return False
                
            return any(cap.get('id') == capability.get('id') for cap in role.get('capabilities', []))
            
        def get_all_capabilities():
            return capabilities
            
        # Add tojson filter for debug
        def tojson(value):
            import json
            return json.dumps(value)
        
        # Render template
        return render_template('entity_editor_debug.html',
                             ontology=ontology,
                             entities=entities,
                             latest_version=latest_version,
                             world_id=world_id,
                             is_editable=is_editable,
                             get_entity_origin=get_entity_origin,
                             is_parent_of=is_parent_of,
                             get_valid_parents=get_valid_parents,
                             has_capability=has_capability,
                             get_all_capabilities=get_all_capabilities,
                             serialized_parents=serialized_parents,
                             serialized_capabilities=serialized_capabilities,
                             tojson=tojson)
    
    # Register the debug route with a different name
    app.register_blueprint(editor_bp, name='ontology_editor_debug')
    print("Debug route added to ontology editor blueprint")
    print("Access at: /ontology-editor-debug/debug?ontology_id=1&view=entities")

if __name__ == '__main__':
    add_debug_route()
