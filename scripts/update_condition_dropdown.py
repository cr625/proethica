"""
Script to update condition dropdown options to ensure condition hierarchy parents 
appear in the entity editor.
This builds on the previous engineering role fix approach.
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
    Update the entity service to ensure all condition parents will appear in dropdowns.
    """
    print("Updating EntityService.get_valid_parents method for conditions...")
    
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
    
    # Replace with enhanced method that adds the condition base classes
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
        
        elif entity_type == 'condition':
            # Add special condition base classes if missing
            condition_base_classes = [
                {
                    'id': "http://proethica.org/ontology/intermediate#ConditionType",
                    'label': "Condition Type"
                },
                {
                    'id': "http://proethica.org/ontology/engineering-ethics#EthicalDilemma",
                    'label': "Ethical Dilemma"
                },
                {
                    'id': "http://proethica.org/ontology/engineering-ethics#Principle",
                    'label': "Principle"
                },
                {
                    'id': "http://proethica.org/ontology/engineering-ethics#SafetyPrinciple",
                    'label': "Safety Principle"
                },
                {
                    'id': "http://proethica.org/ontology/engineering-ethics#ConflictOfInterestCondition",
                    'label': "Conflict of Interest Condition"
                }
            ]
            
            # Add any missing base classes
            for base_class in condition_base_classes:
                if not any(r['id'] == base_class['id'] for r in results):
                    print(f"Adding {base_class['label']} explicitly to condition parent options")
                    results.append(base_class)
        
        # Sort results by label for consistent order
        results.sort(key=lambda x: x['label'])
        
        return results"""
    
    # Replace the return statement
    updated_content = content.replace(results_section, replacement)
    
    # Write the updated content
    with open(entity_service_path, 'w') as f:
        f.write(updated_content)
    
    print("Updated EntityService.get_valid_parents() to ensure condition parent classes appear in dropdown")

def update_is_parent_of_method():
    """
    Update the is_parent_of method to handle condition parent classes correctly.
    """
    print("Updating is_parent_of method to improve condition parent handling...")
    
    # Base paths
    base_dir = os.path.dirname(os.path.dirname(__file__))
    entity_service_path = os.path.join(base_dir, "ontology_editor", "services", "entity_service.py")
    
    with open(entity_service_path, 'r') as f:
        content = f.read()
    
    # Find the is_parent_of class method
    pattern = r'@classmethod\s+def is_parent_of\(cls, parent, entity\):'
    if not re.search(pattern, content):
        print("is_parent_of method not found in EntityService, creating it...")
        
        # Find class definition
        class_def = "class EntityService:"
        class_def_pos = content.find(class_def)
        
        if class_def_pos == -1:
            print("Error: EntityService class definition not found")
            return
        
        # Position after class definition
        insert_pos = class_def_pos + len(class_def)
        
        # Method to add
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
        if not entity or not parent:
            return False
            
        # Ensure consistent string comparison
        parent_id = str(parent.get('id')).strip() if parent.get('id') else None
        entity_parent = str(entity.get('parent_class')).strip() if entity.get('parent_class') else None
        
        # For debugging
        print(f"Comparing parent ID: {parent_id}")
        print(f"With entity parent_class: {entity_parent}")
        print(f"Match: {parent_id == entity_parent}")
        
        if parent_id and entity_parent:
            return parent_id == entity_parent
                
        return False
"""
        
        # Add method after class definition
        updated_content = content[:insert_pos] + method_def + content[insert_pos:]
        
        # Write the updated content
        with open(entity_service_path, 'w') as f:
            f.write(updated_content)
        
        print("Added is_parent_of() method to EntityService")
    else:
        print("is_parent_of method already exists in EntityService")

def update_templates():
    """
    Update condition template to use the updated is_parent_of method.
    """
    print("Updating condition template to use is_parent_of method...")
    
    # Base paths
    base_dir = os.path.dirname(os.path.dirname(__file__))
    conditions_tab_path = os.path.join(base_dir, "ontology_editor", "templates", "partials", "conditions_tab.html")
    
    with open(conditions_tab_path, 'r') as f:
        content = f.read()
    
    # Find the parent selection code
    pattern = r'<select class="form-control" id="parent-\{\{ entity\.id \}\}" name="parent_class" required>.*?</select>'
    
    # Check if the current pattern already uses is_parent_of
    if "is_parent_of" in content:
        print("Template already appears to use is_parent_of method")
        return
    
    # Replace with updated parent selection code
    replacement = """<select class="form-control" id="parent-{{ entity.id }}" name="parent_class" required>
                                {% for parent in get_valid_parents('condition') %}
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
    with open(conditions_tab_path, 'w') as f:
        f.write(updated_content)
    
    print("Updated conditions tab template to use is_parent_of method")

def main():
    """Main function"""
    print("Starting condition dropdown update...")
    
    # Update entity service to include condition base classes
    update_entity_service()
    
    # Update or add is_parent_of method
    update_is_parent_of_method()
    
    # Update template
    update_templates()
    
    print("\nDone! Now you need to:")
    print("1. Restart the server")
    print("2. Clear your browser cache")
    print("3. First run the fix_condition_hierarchy.py script to fix the ontology")
    print("4. Then the condition parent dropdowns should show the correct options")

if __name__ == "__main__":
    main()
