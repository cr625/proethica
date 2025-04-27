#!/usr/bin/env python3
"""
Script to add the current ontology ID to the HTML template for the diff viewer.
"""
import os
import re

def write_diff_currentOntologyId():
    """
    Add the currentOntologyId input to the differential viewer template.
    This ensures the diff viewer knows which ontology to query.
    """
    # Path to the editor HTML template file
    template_file_path = 'ontology_editor/templates/editor.html'
    
    if not os.path.exists(template_file_path):
        print(f"Error: {template_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{template_file_path}.ontology_id.bak'
    print(f"Creating backup of {template_file_path} to {backup_file_path}")
    
    with open(template_file_path, 'r') as f:
        content = f.read()
    
    with open(backup_file_path, 'w') as f:
        f.write(content)
    
    # Check if we need to add the ontology ID input
    if 'id="currentOntologyId"' not in content:
        # Look for the diff modal HTML section
        diff_modal_header_pattern = r'<div class="diff-modal-header">\s*<h5 class="diff-modal-title">Compare Versions</h5>'
        
        if re.search(diff_modal_header_pattern, content):
            # Add the hidden input field with ontology ID
            updated_content = re.sub(
                diff_modal_header_pattern,
                """<div class="diff-modal-header">
                <h5 class="diff-modal-title">Compare Versions</h5>
                <!-- Hidden input to store current ontology ID -->
                <input type="hidden" id="currentOntologyId" value="{{ ontology_id }}">""",
                content
            )
            
            # Write the modified content back
            with open(template_file_path, 'w') as f:
                f.write(updated_content)
            
            print("Added currentOntologyId hidden input to editor template")
            return True
        else:
            print("Could not find diff modal header in template")
            return False
    else:
        print("currentOntologyId input already exists in template")
        return True

if __name__ == "__main__":
    if write_diff_currentOntologyId():
        print("\nCurrentOntologyId input added successfully!")
    else:
        print("\nFailed to add currentOntologyId input. Please check the error messages above.")
