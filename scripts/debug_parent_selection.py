
"""
Debug script to print parent selection details directly to the browser.
This will help identify why parent classes aren't being selected correctly.
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from flask import Flask, render_template, jsonify
from app.services.ontology_entity_service import OntologyEntityService
from ontology_editor.services.entity_service import EntityService  

def run_debug_server():
    """Run a simple debug server to check parent class selection."""
    app = Flask(__name__)
    
    @app.route('/debug/<int:ontology_id>')
    def debug(ontology_id):
        with create_app().app_context():
            # Get entities
            entity_service = OntologyEntityService.get_instance()
            
            # Create a dummy world object
            class DummyWorld:
                def __init__(self, id):
                    self.ontology_id = id
                    
            dummy_world = DummyWorld(ontology_id)
            entities = entity_service.get_entities_for_world(dummy_world)
            
            # Get parents for roles
            parents = EntityService.get_valid_parents(ontology_id, 'role')
            
            # Generate debug info
            debug_info = []
            for role in entities['entities']['roles']:
                debug_info.append({
                    'label': role['label'],
                    'id': role['id'],
                    'parent_class': role.get('parent_class'),
                    'potential_matches': [
                        {
                            'parent_label': p['label'],
                            'parent_id': p['id'],
                            'is_match': role.get('parent_class') == p['id'],
                            'comparison': f"{role.get('parent_class')} == {p['id']}"
                        }
                        for p in parents
                    ]
                })
            
            return jsonify({'debug_info': debug_info})
    
    app.run(debug=True, port=5050)

if __name__ == '__main__':
    run_debug_server()
