"""
Script to fix parent class selection in entity editor templates.
This script adds debug output to entity selection and modifies the templates
to use direct parent_class comparison rather than the is_parent_of helper.
"""
import sys
import os
import re

def fix_parent_class_selection():
    """Fix parent class selection in entity tab templates."""
    print("Fixing parent class selection in entity tab templates...")
    
    # Get all entity tab templates
    base_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "ontology_editor", "templates", "partials")
    tab_templates = [f for f in os.listdir(base_path) if f.endswith('_tab.html')]
    
    for template_name in tab_templates:
        template_path = os.path.join(base_path, template_name)
        print(f"Processing {template_name}...")
        
        # Read template content
        with open(template_path, 'r') as f:
            content = f.read()
        
        # Search for parent class select section
        parent_select_pattern = r'(<select[^>]*name="parent_class"[^>]*>[\s\S]*?</select>)'
        match = re.search(parent_select_pattern, content)
        
        if match:
            # Get the entire select section
            select_section = match.group(1)
            
            # Check if the select section has an option with is_parent_of
            if 'is_parent_of' in select_section:
                # Replace with direct parent_class comparison
                new_select_section = re.sub(
                    r'<option value="([^"]+)"(?: [^>]*)?>([^<]+)</option>',
                    r'''<option value="\1" {% if entity.parent_class == "\1" %}selected{% endif %}>
                        \2
                    </option>''',
                    select_section
                )
                
                # Also add debug comment
                new_select_section = f'''
                <!-- Parent class debug:
                     Entity: {{{{ entity.label }}}}
                     Parent Class: {{{{ entity.parent_class }}}}
                -->
                {new_select_section}
                '''
                
                # Replace the original select section with the new one
                new_content = content.replace(select_section, new_select_section)
                
                # Write the modified content back
                with open(template_path, 'w') as f:
                    f.write(new_content)
                
                print(f"  Updated parent class select in {template_name}")
            else:
                print(f"  No parent class select with is_parent_of found in {template_name}")
        else:
            print(f"  No parent class select found in {template_name}")
    
    print("Done fixing parent class selection.")

if __name__ == '__main__':
    fix_parent_class_selection()
