#!/usr/bin/env python
"""
Restore the editor.js file from the version_api.bak backup.
This script will restore the last known good version of the editor.js file
but keep the proper ACE editor option names.
"""
import os
import re

def restore_editor():
    """
    Restore editor.js from backup and ensure ACE editor options are correct.
    """
    js_file_path = 'ontology_editor/static/js/editor.js'
    backup_path = 'ontology_editor/static/js/editor.js.version_api.bak'
    
    if not os.path.exists(backup_path):
        print(f"Error: Backup file {backup_path} not found")
        return False
        
    # Create a new backup of the current file before restoration
    current_backup_path = 'ontology_editor/static/js/editor.js.current_state.bak'
    print(f"Creating backup of current file at {current_backup_path}")
    with open(js_file_path, 'r') as f:
        current_content = f.read()
    
    with open(current_backup_path, 'w') as f:
        f.write(current_content)
    
    # Read the backup file
    with open(backup_path, 'r') as f:
        backup_content = f.read()
    
    # Ensure ACE editor options are correct
    fixed_content = re.sub(
        r'enableBasicAutoComplete:\s*true',
        'enableBasicAutocompletion: true',
        backup_content
    )
    
    fixed_content = re.sub(
        r'enableLiveAutoComplete:\s*true',
        'enableLiveAutocompletion: true',
        fixed_content
    )
    
    # Write the restored content with fixed options
    with open(js_file_path, 'w') as f:
        f.write(fixed_content)
    
    print(f"Successfully restored {js_file_path} from {backup_path} with corrected ACE editor options")
    return True

if __name__ == "__main__":
    if restore_editor():
        print("Restoration completed successfully")
    else:
        print("Restoration failed")
