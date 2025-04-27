#!/usr/bin/env python3
"""
Script to fix the constant variable reassignment in diff.js.
"""
import os
import re

def fix_const_reassignment():
    """
    Fix the 'Assignment to constant variable' error in diff.js by replacing
    const with let for variables that need to be modified.
    """
    # Path to the diff.js file
    js_file_path = 'ontology_editor/static/js/diff.js'
    
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{js_file_path}.const_fix.bak'
    print(f"Creating backup of {js_file_path} to {backup_file_path}")
    
    with open(js_file_path, 'r') as f:
        content = f.read()
    
    with open(backup_file_path, 'w') as f:
        f.write(content)
    
    # Fix constant variable assignments
    updated_content = content
    
    # 1. Fix the version validation code where fromVersion and toVersion are modified
    version_validation_patterns = [
        r'const fromVersion\s*=\s*document\.getElementById\(\'diffFromVersion\'\)\.value;([^}]*?)fromVersion\s*=\s*fromVersion\.toString\(\)\.trim\(\);',
        r'const fromVersion\s*=\s*this\.value;([^}]*?)fromVersion\s*=\s*fromVersion\.toString\(\)\.trim\(\);',
        r'const toVersion\s*=\s*document\.getElementById\(\'diffToVersion\'\)\.value;([^}]*?)toVersion\s*=\s*toVersion\.toString\(\)\.trim\(\);',
        r'const toVersion\s*=\s*this\.value;([^}]*?)toVersion\s*=\s*toVersion\.toString\(\)\.trim\(\);',
    ]
    
    for pattern in version_validation_patterns:
        # Change const to let for variables that are modified later
        updated_content = re.sub(pattern, lambda m: m.group(0).replace('const ', 'let '), updated_content)
    
    # 2. More direct approach - change all version variable declarations from const to let
    variable_declarations = [
        (r'const fromVersion\s*=\s*document\.getElementById\(\'diffFromVersion\'\)\.value;', 'let fromVersion = document.getElementById(\'diffFromVersion\').value;'),
        (r'const fromVersion\s*=\s*this\.value;', 'let fromVersion = this.value;'),
        (r'const toVersion\s*=\s*document\.getElementById\(\'diffToVersion\'\)\.value;', 'let toVersion = document.getElementById(\'diffToVersion\').value;'),
        (r'const toVersion\s*=\s*this\.value;', 'let toVersion = this.value;'),
    ]
    
    for pattern, replacement in variable_declarations:
        updated_content = re.sub(pattern, replacement, updated_content)
    
    # Write the modified content back
    with open(js_file_path, 'w') as f:
        f.write(updated_content)
    
    print("Changed 'const' to 'let' for variables that need to be modified")
    return True

if __name__ == "__main__":
    if fix_const_reassignment():
        print("\nConstant reassignment fix applied successfully!")
    else:
        print("\nFailed to apply constant reassignment fix. Please check the error messages above.")
