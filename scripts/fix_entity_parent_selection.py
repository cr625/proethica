"""
Script to fix entity parent class selection in the entity editor.
This script directly modifies the necessary template files to ensure
correct parent class selection without relying on the helper function.
"""
import sys
import os
import re

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def fix_entity_parent_selection():
    """Fix parent class selection in entity templates."""
    print("Fixing parent class selection in entity templates...")
    
    # Base paths
    base_dir = os.path.dirname(os.path.dirname(__file__))
    template_dir = os.path.join(base_dir, "ontology_editor", "templates", "partials")
    entity_types = ['roles', 'conditions', 'resources', 'actions', 'events', 'capabilities']
    
    for entity_type in entity_types:
        template_path = os.path.join(template_dir, f"{entity_type}_tab.html")
        if not os.path.exists(template_path):
            print(f"Template not found: {template_path}")
            continue
            
        print(f"Processing {entity_type}_tab.html...")
        
        # Read original content
        with open(template_path, 'r') as f:
            content = f.read()
        
        # Update the parent class selector to ensure direct comparison
        updated_content = content
        
        # First fix - ensure Jinja2 comparison is strict and direct
        updated_content = re.sub(
            r'<option value="{{ parent\.id }}" {% if entity\.parent_class == parent\.id %}selected{% endif %}>',
            r'<option value="{{ parent.id }}" {% if entity.parent_class == parent.id|string %}selected{% endif %}>',
            updated_content
        )
        
        # Second fix - remove quotes in existing comparisons
        updated_content = re.sub(
            r'<option value="{{ parent\.id }}" {% if entity\.parent_class == "{{ parent\.id }}" %}selected{% endif %}>',
            r'<option value="{{ parent.id }}" {% if entity.parent_class == parent.id|string %}selected{% endif %}>',
            updated_content
        )
        
        # Write updated content
        if updated_content != content:
            with open(template_path, 'w') as f:
                f.write(updated_content)
            print(f"  Updated template: {entity_type}_tab.html")
        else:
            print(f"  No changes needed for: {entity_type}_tab.html")
    
    # Now update the entity service that supplies parent class values
    entity_service_path = os.path.join(base_dir, "ontology_editor", "services", "entity_service.py")
    if os.path.exists(entity_service_path):
        print("Updating EntityService.get_valid_parents()...")
        
        with open(entity_service_path, 'r') as f:
            service_content = f.read()
        
        # Ensure the parent.id is returned as a string for consistent comparison
        if "results.append({" in service_content and "'id': str(instance)," in service_content:
            # Function already returns strings for IDs - no change needed
            print("  EntityService already returns string IDs - no change needed")
        else:
            # Add fix to ensure string IDs
            updated_service = re.sub(
                r"results\.append\(\{\s*'id': ([^,]+),", 
                r"results.append({\n                'id': str(\1),", 
                service_content
            )
            
            if updated_service != service_content:
                with open(entity_service_path, 'w') as f:
                    f.write(updated_service)
                print("  Updated EntityService to ensure string IDs")
            else:
                print("  Could not update EntityService - manual inspection needed")
    
    # Also update helpers in __init__.py
    init_path = os.path.join(base_dir, "ontology_editor", "__init__.py")
    if os.path.exists(init_path):
        print("Updating is_parent_of helper function...")
        
        with open(init_path, 'r') as f:
            init_content = f.read()
        
        # Update the is_parent_of helper function to use string comparison
        init_updated = re.sub(
            r"return parent\.get\('id'\) == entity\.get\('parent_class'\)",
            r"return str(parent.get('id')) == str(entity.get('parent_class'))",
            init_content
        )
        
        if init_updated != init_content:
            with open(init_path, 'w') as f:
                f.write(init_updated)
            print("  Updated is_parent_of helper function")
        else:
            print("  No changes needed for is_parent_of helper function")
    
    print("Done fixing parent class selection.")
    print("\nTo apply these changes, restart the server and clear browser cache.")

if __name__ == '__main__':
    fix_entity_parent_selection()
