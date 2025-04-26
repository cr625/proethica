#!/usr/bin/env python
"""
Fix the ACE editor options in editor.js to use the correct names.
This ensures the options are properly set as:
- enableBasicAutocompletion (not enableBasicAutoComplete)
- enableLiveAutocompletion (not enableLiveAutoComplete)
"""
import os
import re

def fix_ace_options():
    """
    Fix the ACE editor options in editor.js.
    """
    js_file_path = 'ontology_editor/static/js/editor.js'
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create a backup if one doesn't already exist
    backup_file_path = 'ontology_editor/static/js/editor.js.ace_options.bak'
    if not os.path.exists(backup_file_path):
        print(f"Creating backup of {js_file_path} to {backup_file_path}")
        with open(js_file_path, 'r') as f:
            original_content = f.read()
        
        with open(backup_file_path, 'w') as f:
            f.write(original_content)
    else:
        # Read the current content
        with open(js_file_path, 'r') as f:
            original_content = f.read()
    
    # Fix the misspelled options
    fixed_content = re.sub(
        r'enableBasicAutoComplete:\s*true',
        'enableBasicAutocompletion: true',
        original_content
    )
    
    fixed_content = re.sub(
        r'enableLiveAutoComplete:\s*true',
        'enableLiveAutocompletion: true',
        fixed_content
    )
    
    # Only write the file if changes were made
    if fixed_content != original_content:
        with open(js_file_path, 'w') as f:
            f.write(fixed_content)
        print("Fixed ACE editor options")
        return True
    else:
        print("ACE editor options already correct, no changes needed")
        return True

if __name__ == "__main__":
    if fix_ace_options():
        print("Successfully updated ACE editor options")
    else:
        print("Failed to update ACE editor options")
