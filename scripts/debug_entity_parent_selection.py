"""
Script to debug entity parent class selection in the entity editor.
This adds detailed debugging output to the roles tab to verify that the 
correct parent class is being selected.
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def create_debug_roles_tab():
    """Create a debug version of the roles tab template."""
    print("Creating debug version of roles_tab.html...")
    
    # Base paths
    base_dir = os.path.dirname(os.path.dirname(__file__))
    template_dir = os.path.join(base_dir, "ontology_editor", "templates", "partials")
    
    # Original and debug file paths
    original_path = os.path.join(template_dir, "roles_tab.html")
    debug_path = os.path.join(template_dir, "roles_tab_debug.html")
    
    # Read original content
    with open(original_path, 'r') as f:
        content = f.read()
    
    # Add debug header
    debug_header = """
<!-- DEBUG VERSION OF ROLES TAB -->
<!-- 
This template includes detailed debugging output to help diagnose 
parent class selection issues. It shows the parent.id and entity.parent_class
values for each option in each parent dropdown.
-->

    """
    content = debug_header + content
    
    # Modify the parent class selector to show debug information
    # Look for the parent selector in the edit form
    selector_pattern = """<select class="form-control" id="parent-{{ entity.id }}" name="parent_class" required>
                                <!-- Debug info - will show in HTML source -->
                                <!-- Entity Parent Class: {{ entity.parent_class }} -->
                                
                                {% for parent in get_valid_parents('role') %}
                                <option value="{{ parent.id }}" {% if entity.parent_class == parent.id %}selected{% endif %}>
                                    {{ parent.label }}
                                </option>
                                {% endfor %}
                            </select>"""
    
    # Replace with enhanced debug version
    debug_selector = """<select class="form-control" id="parent-{{ entity.id }}" name="parent_class" required>
                                <!-- ENHANCED DEBUG INFO -->
                                <option value="" disabled>DEBUGGING INFO - ENTITY: {{ entity.label }}</option>
                                <option value="" disabled>Entity parent_class: "{{ entity.parent_class }}"</option>
                                <option value="" disabled>-----------------------------------</option>
                                
                                {% for parent in get_valid_parents('role') %}
                                {% set match = entity.parent_class == parent.id %}
                                <option value="{{ parent.id }}" {% if match %}selected{% endif %}>
                                    {{ parent.label }} {% if match %}✓MATCH{% endif %}
                                    {% if not match %}(NO MATCH){% endif %}
                                </option>
                                {% endfor %}
                            </select>
                            
                            <!-- String comparison debugging -->
                            <div class="text-muted small mt-1" style="background: #f8f9fa; padding: 5px; border-radius: 3px;">
                                <strong>Debug comparison:</strong><br>
                                {% for parent in get_valid_parents('role') %}
                                <pre>{{ parent.id|tojson }} == {{ entity.parent_class|tojson }} : {{ (parent.id == entity.parent_class)|tojson }}</pre>
                                {% if loop.index > 5 %}{% break %}{% endif %}
                                {% endfor %}
                            </div>"""
    
    # Replace selector in content
    debug_content = content.replace(selector_pattern, debug_selector)
    
    # Write debug file
    with open(debug_path, 'w') as f:
        f.write(debug_content)
    
    print(f"Debug template created at: {debug_path}")
    print("To use it, replace the roles_tab.html include in entity_editor.html with roles_tab_debug.html")
    
    # Also make a copy of entity_editor.html 
    entity_editor_path = os.path.join(base_dir, "ontology_editor", "templates", "entity_editor.html")
    entity_editor_debug_path = os.path.join(base_dir, "ontology_editor", "templates", "entity_editor_debug.html")
    
    with open(entity_editor_path, 'r') as f:
        entity_editor_content = f.read()
    
    # Replace the include of roles_tab.html with roles_tab_debug.html
    debug_entity_editor = entity_editor_content.replace(
        "{% include 'partials/roles_tab.html' %}",
        "{% include 'partials/roles_tab_debug.html' %}"
    )
    
    with open(entity_editor_debug_path, 'w') as f:
        f.write(debug_entity_editor)
    
    print(f"Debug entity editor created at: {entity_editor_debug_path}")
    print("You can now access the debug version at: /ontology-editor/debug?ontology_id=1&view=entities")
    
    # Create debug route
    debug_route_path = os.path.join(base_dir, "scripts", "add_debug_route.py")
    debug_route = """
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import render_template, request
from app import create_app
from ontology_editor import create_ontology_editor_blueprint

def add_debug_route():
    \"\"\"Add debug route to ontology editor blueprint.\"\"\"
    app = create_app()
    editor_bp = create_ontology_editor_blueprint()
    
    @editor_bp.route('/debug')
    def debug_entity_editor():
        \"\"\"Debug version of entity editor view.\"\"\"
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
    
    # Register the debug route
    app.register_blueprint(editor_bp)
    print("Debug route added to ontology editor blueprint")
    print("Access at: /ontology-editor/debug?ontology_id=1&view=entities")

if __name__ == '__main__':
    add_debug_route()
"""
    
    with open(debug_route_path, 'w') as f:
        f.write(debug_route)
    
    print(f"Debug route script created at: {debug_route_path}")
    print("Run it with: python scripts/add_debug_route.py")

if __name__ == '__main__':
    create_debug_roles_tab()
