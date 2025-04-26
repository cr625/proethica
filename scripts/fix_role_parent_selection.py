"""
Script to fix role parent selection in entity editor.
This addresses the issue where all roles show "Structural Engineer Role" as parent even when they have other parents.
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology
from rdflib import Graph, Namespace, RDF, RDFS
import re

def fix_entity_editor_templates():
    """
    Fix entity editor templates to correctly select parent classes.
    This modifies the templates to ensure the comparison is done correctly.
    """
    print("Fixing entity editor templates...")
    
    # Base paths
    base_dir = os.path.dirname(os.path.dirname(__file__))
    partials_dir = os.path.join(base_dir, "ontology_editor", "templates", "partials")
    
    # Get all tab templates
    tab_templates = [f for f in os.listdir(partials_dir) if f.endswith('_tab.html')]
    
    # Find the pattern to replace in each template
    pattern = r'<option value="{{ parent\.id }}" {% if (entity\.parent_class == parent\.id(\|string)?|is_parent_of\(parent, entity\)) %}selected{% endif %}>(.+?)</option>'
    
    # New version with exact URI matching and better debugging
    replacement = r'''<option value="{{ parent.id }}" 
        {%- if entity.parent_class and parent.id and entity.parent_class == parent.id %}selected{% endif %}>
        {{- parent.label }}
        <!-- DEBUG: parent.id: {{ parent.id }} -->
    </option>'''
    
    for template_file in tab_templates:
        file_path = os.path.join(partials_dir, template_file)
        print(f"Processing {template_file}...")
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Use regex to find and replace the pattern
        new_content = re.sub(pattern, replacement, content)
        
        # Add debug information for troubleshooting
        debug_comment = """
<!-- 
PARENT CLASS DEBUG:
This template has been modified by fix_role_parent_selection.py to ensure correct parent selection.
The template now uses direct string comparison for parent.id and entity.parent_class.
-->
"""
        if '<!--' not in new_content[:200]:
            new_content = debug_comment + new_content
        
        with open(file_path, 'w') as f:
            f.write(new_content)
        
        print(f"  Updated {template_file}")

def fix_init_helpers():
    """
    Fix the helper functions in __init__.py to ensure correct parent class selection.
    """
    print("Fixing helper functions in __init__.py...")
    
    # Base paths
    base_dir = os.path.dirname(os.path.dirname(__file__))
    init_path = os.path.join(base_dir, "ontology_editor", "__init__.py")
    
    with open(init_path, 'r') as f:
        content = f.read()
    
    # Find is_parent_of function in entity_editor
    entity_editor_pattern = r'def is_parent_of\(parent, entity\):[^}]*?return ([^}]*?)$'
    entity_editor_replacement = """def is_parent_of(parent, entity):
            if not entity or not parent:
                return False
                
            # Ensure consistent string comparison
            parent_id = str(parent.get('id')).strip() if parent.get('id') else None
            entity_parent = str(entity.get('parent_class')).strip() if entity.get('parent_class') else None
            
            # Debug output to help troubleshoot
            print(f"Comparing parent: {parent_id}")
            print(f"With entity parent: {entity_parent}")
            print(f"Match: {parent_id == entity_parent}")
            
            if parent_id and entity_parent:
                return parent_id == entity_parent
                
            return False"""
    
    # Apply the replacement
    new_content = re.sub(entity_editor_pattern, entity_editor_replacement, content, flags=re.MULTILINE | re.DOTALL)
    
    # Find is_parent_of function in partial template endpoint
    partial_pattern = r'def is_parent_of\(parent, entity\):[^}]*?return ([^}]*?)$'
    partial_replacement = """def is_parent_of(parent, entity):
            if not entity or not parent:
                return False
                
            # Ensure consistent string comparison
            parent_id = str(parent.get('id')).strip() if parent.get('id') else None
            entity_parent = str(entity.get('parent_class')).strip() if entity.get('parent_class') else None
            
            # Debug output to help troubleshoot
            print(f"Partial template comparing parent: {parent_id}")
            print(f"With entity parent: {entity_parent}")
            print(f"Match: {parent_id == entity_parent}")
            
            if parent_id and entity_parent:
                return parent_id == entity_parent
                
            return False"""
    
    # Apply the second replacement (only after the entity_editor function)
    new_content = new_content.replace("def is_parent_of(parent, entity):", 
                                      "def is_parent_of(parent, entity):", 1)  # Keep the first occurrence
    new_content = new_content.replace("def is_parent_of(parent, entity):", 
                                      partial_replacement, 1)  # Replace the second occurrence
    
    with open(init_path, 'w') as f:
        f.write(new_content)
    
    print("  Updated helper functions in __init__.py")

def fix_entity_service():
    """
    Add debugging and fix issue in entity service code.
    """
    print("Adding debugging to entity service...")
    
    # Base paths
    base_dir = os.path.dirname(os.path.dirname(__file__))
    entity_service_path = os.path.join(base_dir, "ontology_editor", "services", "entity_service.py")
    
    with open(entity_service_path, 'r') as f:
        content = f.read()
    
    # Find get_valid_parents method and add debug output
    pattern = r'@classmethod\s+def get_valid_parents\(cls, ontology_id, entity_type\):[^}]*?return results'
    replacement = """@classmethod
    def get_valid_parents(cls, ontology_id, entity_type):
        \"\"\"
        Get valid parent classes for a given entity type
        
        Args:
            ontology_id (int): Ontology ID
            entity_type (str): Entity type ('role', 'condition', etc.)
            
        Returns:
            list: List of valid parent classes
        \"\"\"
        # Get the ontology
        ontology = Ontology.query.get(ontology_id)
        if not ontology:
            return []
            
        # Parse the ontology content
        g = Graph()
        g.parse(data=ontology.content, format="turtle")
        
        # Debug output
        print(f"Getting valid parents for {entity_type} in ontology {ontology_id}")
        
        # Determine namespace patterns from data
        namespaces = {}
        for prefix, ns in g.namespaces():
            namespaces[prefix] = ns
        
        # Try to find the class type URI from common patterns
        class_type = cls.ENTITY_TYPES.get(entity_type)
        if not class_type:
            return []
        
        # Get all instances of the class type
        class_instances = []
        
        # Common base URIs to check
        base_uris = [
            'http://purl.obolibrary.org/obo/BFO_',
            'http://proethica.org/ontology/intermediate#',
            'http://proethica.org/ontology/engineering-ethics#'
        ]
        
        # Try with common URIs first
        for base_uri in base_uris:
            try:
                class_uri = URIRef(f"{base_uri}{class_type}")
                class_instances.extend(g.subjects(RDF.type, class_uri))
            except Exception as e:
                print(f"Error with {base_uri}: {e}")
        
        # Check for domain-specific namespaces
        for prefix, ns in g.namespaces():
            try:
                # ns is already a Namespace object with __getitem__ defined
                class_uri = ns[class_type]
                class_instances.extend(g.subjects(RDF.type, class_uri))
            except Exception as e:
                pass
        
        # Get information about each instance
        results = []
        for instance in class_instances:
            label = next(g.objects(instance, RDFS.label), None)
            label = str(label) if label else str(instance).split('#')[-1]
            
            # Clean the instance string to ensure consistent formatting
            instance_str = str(instance).strip()
            
            parent_entry = {
                'id': instance_str,
                'label': label
            }
            
            results.append(parent_entry)
            print(f"Found parent option: {label} with ID: {instance_str}")
           
        # Ensure results are sorted by label for consistent order
        results.sort(key=lambda x: x['label'])
        
        return results"""
    
    # Apply the replacement
    new_content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
    
    with open(entity_service_path, 'w') as f:
        f.write(new_content)
    
    print("  Updated entity service code with debugging")

def create_debug_script():
    """
    Create a debug script to directly check parent-child relationships in browser.
    """
    print("Creating debug script...")
    
    # Base paths
    base_dir = os.path.dirname(os.path.dirname(__file__))
    debug_dir = os.path.join(base_dir, "scripts")
    debug_path = os.path.join(debug_dir, "debug_parent_selection.py")
    
    debug_content = """
\"\"\"
Debug script to print parent selection details directly to the browser.
This will help identify why parent classes aren't being selected correctly.
\"\"\"
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from flask import Flask, render_template, jsonify
from app.services.ontology_entity_service import OntologyEntityService
from ontology_editor.services.entity_service import EntityService  

def run_debug_server():
    \"\"\"Run a simple debug server to check parent class selection.\"\"\"
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
"""
    
    with open(debug_path, 'w') as f:
        f.write(debug_content)
    
    print(f"  Created debug script at scripts/debug_parent_selection.py")
    
def main():
    """Main function"""
    print("Starting parent class selection fix...")
    
    # Fix entity editor templates
    fix_entity_editor_templates()
    
    # Fix helper functions
    fix_init_helpers()
    
    # Fix entity service
    fix_entity_service()
    
    # Create debug script
    create_debug_script()
    
    print("\nDone! To apply these changes, please:")
    print("1. Restart the server")
    print("2. Clear your browser cache")
    print("3. Refresh the entity editor page")

if __name__ == '__main__':
    main()
