#!/usr/bin/env python3

import os
import sys

def fix_version_loading_direct():
    """
    Directly fix the version loading issue by replacing specific lines in the file.
    This approach is more targeted than using regex patterns.
    """
    # Path to the editor.js file
    js_file_path = 'ontology_editor/static/js/editor.js'
    
    # Check if the file exists
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{js_file_path}.direct_fix.bak'
    print(f"Creating backup of {js_file_path} to {backup_file_path}")
    
    with open(js_file_path, 'r') as f:
        lines = f.readlines()
        
    with open(backup_file_path, 'w') as f:
        f.writelines(lines)
    
    # Make the necessary changes
    fixed_lines = []
    changes_made = {
        'function_signature': False,
        'fetch_url': False,
        'version_item_selector': False
    }
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Fix function signature for loadVersion
        if ' * @param {string} versionId - ID of the version to load' in line:
            fixed_lines.append(' * @param {string} versionNumber - Number of the version to load\n')
            changes_made['function_signature'] = True
        # Fix function definition
        elif 'function loadVersion(versionId) {' in line:
            fixed_lines.append('function loadVersion(versionNumber) {\n')
            changes_made['function_signature'] = True
        # Fix fetch URL
        elif '    fetch(`/ontology-editor/api/versions/${versionId}`)' in line:
            fixed_lines.append('    fetch(`/ontology-editor/api/versions/${currentOntologyId}/${versionNumber}`)\n')
            changes_made['fetch_url'] = True
        # Fix version item selector
        elif '    const versionItem = document.querySelector(`#versionList li[data-version-id="${versionId}"]`);' in line:
            fixed_lines.append('    const versionItem = document.querySelector(`#versionList li[data-version-number="${versionNumber}"]`);\n')
            changes_made['version_item_selector'] = True
        else:
            fixed_lines.append(line)
        
        i += 1
    
    # Report on changes made
    for key, value in changes_made.items():
        if value:
            print(f"✅ Fixed {key}")
        else:
            print(f"❌ Did not fix {key}")
    
    # Write the fixed content back to the file
    with open(js_file_path, 'w') as f:
        f.writelines(fixed_lines)
    
    if all(changes_made.values()):
        print("All necessary changes were made successfully")
        return True
    else:
        print("Some changes were not made. The fix may not be complete.")
        return False

if __name__ == "__main__":
    if fix_version_loading_direct():
        print("\nFix applied successfully!")
    else:
        print("\nFailed to apply complete fix. Please check the error messages above.")
