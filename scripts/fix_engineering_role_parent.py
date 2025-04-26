"""
Script to ensure EngineeringRole appears as a valid parent option in the entity editor.
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology import Ontology
from rdflib import Graph, Namespace, RDF, RDFS
import re

def fix_get_valid_parents_method():
    """
    Fix the get_valid_parents method in EntityService to ensure EngineeringRole appears
    as a valid parent option.
    """
    print("Fixing get_valid_parents method to ensure EngineeringRole appears...")
    
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
    
    # Find the section where we filter results
    results_section = "return results"
    
    # Replace with enhanced method that adds the EngineeringRole
    replacement = """        # Add special base classes if they're missing
        if entity_type == 'role':
            # Check if EngineeringRole is already in results
            eng_role_id = "http://proethica.org/ontology/engineering-ethics#EngineeringRole"
            eng_role_in_results = any(r['id'] == eng_role_id for r in results)
            
            if not eng_role_in_results:
                # Add EngineeringRole explicitly
                print("Adding EngineeringRole explicitly to parent options")
                results.append({
                    'id': eng_role_id,
                    'label': "Engineering Role"
                })
                
            # Also add intermediate Role if needed
            int_role_id = "http://proethica.org/ontology/intermediate#Role"
            int_role_in_results = any(r['id'] == int_role_id for r in results)
            
            if not int_role_in_results:
                # Add intermediate Role explicitly
                print("Adding intermediate Role explicitly to parent options")
                results.append({
                    'id': int_role_id,
                    'label': "Role (Base)"
                })
        
        # Sort results by label for consistent order
        results.sort(key=lambda x: x['label'])
        
        return results"""
    
    # Replace the return statement
    updated_content = content.replace(results_section, replacement)
    
    # Write the updated content
    with open(entity_service_path, 'w') as f:
        f.write(updated_content)
    
    print("Updated EntityService.get_valid_parents() to ensure EngineeringRole appears")

def fix_entity_service_debugging():
    """
    Add better debugging to EntityService for parent class selection.
    """
    print("Adding debugging for parent class selection...")
    
    # Base paths
    base_dir = os.path.dirname(os.path.dirname(__file__))
    entity_service_path = os.path.join(base_dir, "ontology_editor", "services", "entity_service.py")
    
    with open(entity_service_path, 'r') as f:
        content = f.read()
    
    # Find the is_parent_of class method
    pattern = r'@classmethod\s+def is_parent_of\(cls, parent, entity\):'
    if not re.search(pattern, content):
        # Method doesn't exist, so add it
        class_def_end = re.search(r'class EntityService:', content).end()
        
        # Add the is_parent_of method just after the class definition
        method_def = """
    @classmethod
    def is_parent_of(cls, parent, entity):
        \"\"\"
        Check if parent is the parent of an entity.
        Used for selecting the correct parent in the dropdown.
        
        Args:
            parent (dict): Parent entity data
            entity (dict): Entity data
            
        Returns:
            bool: True if parent is the parent of entity
        \"\"\"
        if not parent or not entity:
            return False
            
        # Debug output
        print(f"Comparing parent ID: {parent.get('id')}")
        print(f"With entity parent_class: {entity.get('parent_class')}")
        
        # Ensure consistent string comparison
        parent_id = str(parent.get('id')).strip() if parent.get('id') else None
        entity_parent = str(entity.get('parent_class')).strip() if entity.get('parent_class') else None
        
        print(f"Cleaned comparison: '{parent_id}' == '{entity_parent}'")
        print(f"Result: {parent_id == entity_parent}")
        
        return parent_id == entity_parent
"""
        
        updated_content = content[:class_def_end] + method_def + content[class_def_end:]
        
        # Write the updated content
        with open(entity_service_path, 'w') as f:
            f.write(updated_content)
        
        print("Added is_parent_of method to EntityService")
    else:
        print("is_parent_of method already exists in EntityService")

def update_templates_to_use_service_method():
    """
    Update templates to use the EntityService.is_parent_of method.
    """
    print("Updating templates to use EntityService.is_parent_of method...")
    
    # Base paths
    base_dir = os.path.dirname(os.path.dirname(__file__))
    partials_dir = os.path.join(base_dir, "ontology_editor", "templates", "partials")
    
    # Get all tab templates
    tab_templates = [f for f in os.listdir(partials_dir) if f.endswith('_tab.html')]
    
    for template_file in tab_templates:
        file_path = os.path.join(partials_dir, template_file)
        print(f"Processing {template_file}...")
        
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Update the parent selection to use is_parent_of
        updated_content = re.sub(
            r'{%- if entity\.parent_class and parent\.id and entity\.parent_class == parent\.id %}selected{% endif %}',
            '{% if is_parent_of(parent, entity) %}selected{% endif %}',
            content
        )
        
        if updated_content != content:
            with open(file_path, 'w') as f:
                f.write(updated_content)
            print(f"  Updated {template_file} to use is_parent_of method")
        else:
            print(f"  No changes needed for {template_file}")

def main():
    """Main function"""
    print("Starting EngineeringRole parent fix...")
    
    # Fix get_valid_parents method
    fix_get_valid_parents_method()
    
    # Fix entity service debugging
    fix_entity_service_debugging()
    
    # Update templates
    update_templates_to_use_service_method()
    
    print("\nDone! You'll need to restart the server to apply these changes.")
    print("To test the fix, visit the entity editor and check if EngineeringRole now appears as a parent option.")

if __name__ == '__main__':
    main()
