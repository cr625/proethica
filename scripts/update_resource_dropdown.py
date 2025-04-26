"""
Script to update resource dropdown options to ensure resource hierarchy parents 
appear in the entity editor.
This builds on the previous approach used for roles and conditions.
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology
from rdflib import Graph, Namespace, URIRef, RDF, RDFS
import re

def update_entity_service():
    """
    Update the entity service to ensure all resource parents will appear in dropdowns.
    """
    print("Updating EntityService.get_valid_parents method for resources...")
    
    # Base paths
    base_dir = os.path.dirname(os.path.dirname(__file__))
    entity_service_path = os.path.join(base_dir, "ontology_editor", "services", "entity_service.py")
    
    with open(entity_service_path, 'r') as f:
        content = f.read()
    
    # Find the get_valid_parents method
    pattern = r'@classmethod\s+def get_valid_parents\(cls, ontology_id, entity_type\):'
    if not re.search(pattern, content):
        print("Error: get_valid_parents method not found in EntityService")
        return
    
    # Check if we already have resource handling
    if 'elif entity_type == \'resource\'' in content:
        print("Resource handling already exists in get_valid_parents")
        return
        
    # Find the section where we filter results for conditions
    condition_section = "elif entity_type == 'condition':"
    if condition_section not in content:
        print("Error: condition section not found in get_valid_parents")
        return
    
    # Add resource section after condition section
    resource_section = """
        elif entity_type == 'resource':
            # Add special resource base classes if missing
            resource_base_classes = [
                {
                    'id': "http://proethica.org/ontology/intermediate#ResourceType",
                    'label': "Resource Type"
                },
                {
                    'id': "http://proethica.org/ontology/engineering-ethics#EngineeringDocument",
                    'label': "Engineering Document"
                },
                {
                    'id': "http://proethica.org/ontology/engineering-ethics#EngineeringDrawing",
                    'label': "Engineering Drawing"
                },
                {
                    'id': "http://proethica.org/ontology/engineering-ethics#EngineeringSpecification",
                    'label': "Engineering Specification"
                },
                {
                    'id': "http://proethica.org/ontology/engineering-ethics#EngineeringReport",
                    'label': "Engineering Report"
                },
                {
                    'id': "http://proethica.org/ontology/engineering-ethics#BuildingCode",
                    'label': "Building Code"
                }
            ]
            
            # Add any missing base classes
            for base_class in resource_base_classes:
                if not any(r['id'] == base_class['id'] for r in results):
                    print(f"Adding {base_class['label']} explicitly to resource parent options")
                    results.append(base_class)"""
    
    # Insert resource section after condition section
    updated_content = content.replace(condition_section, condition_section + resource_section)
    
    # Write the updated content
    with open(entity_service_path, 'w') as f:
        f.write(updated_content)
    
    print("Updated EntityService.get_valid_parents() to ensure resource parent classes appear in dropdown")

def update_templates():
    """
    Update resource template to use the is_parent_of method.
    """
    print("Updating resource template to use is_parent_of method...")
    
    # Base paths
    base_dir = os.path.dirname(os.path.dirname(__file__))
    resources_tab_path = os.path.join(base_dir, "ontology_editor", "templates", "partials", "resources_tab.html")
    
    with open(resources_tab_path, 'r') as f:
        content = f.read()
    
    # Find the parent selection code
    pattern = r'<select class="form-control" id="parent-\{\{ entity\.id \}\}" name="parent_class" required>.*?</select>'
    
    # Check if the current pattern already uses is_parent_of
    if "is_parent_of" in content:
        print("Template already appears to use is_parent_of method")
        return
    
    # Replace with updated parent selection code
    replacement = """<select class="form-control" id="parent-{{ entity.id }}" name="parent_class" required>
                                {% for parent in get_valid_parents('resource') %}
                                <option value="{{ parent.id }}" {% if is_parent_of(parent, entity) %}selected{% endif %}>
                                    <!-- DEBUG: parent.id: {{ parent.id }} -->
                                    {{ parent.label }}
                                </option>
                                {% endfor %}
                            </select>"""
    
    # Use a more relaxed regex with DOTALL flag to match multiline content
    updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Check if anything was actually replaced
    if updated_content == content:
        print("Warning: No changes made to template. Pattern may not have matched.")
        return
    
    # Write the updated content
    with open(resources_tab_path, 'w') as f:
        f.write(updated_content)
    
    print("Updated resources tab template to use is_parent_of method")

def main():
    """Main function"""
    print("Starting resource dropdown update...")
    
    # Update entity service to include resource base classes
    update_entity_service()
    
    # Update template
    update_templates()
    
    print("\nDone! Now you need to:")
    print("1. Restart the server")
    print("2. Clear your browser cache")
    print("3. First run the fix_resource_hierarchy.py script to fix the ontology")
    print("4. Then the resource parent dropdowns should show the correct options")

if __name__ == "__main__":
    main()
