#!/usr/bin/env python3
"""
Script to fix the docstring syntax error in routes.py.
"""
import os
import re
import sys

def fix_docstring_syntax():
    """
    Fix the docstring syntax error in the routes.py file.
    """
    # Path to the routes file
    routes_file_path = 'ontology_editor/api/routes.py'
    
    # Check if the file exists
    if not os.path.exists(routes_file_path):
        print(f"Error: {routes_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{routes_file_path}.docstring_fix.bak'
    print(f"Creating backup of {routes_file_path} to {backup_file_path}")
    
    with open(routes_file_path, 'r') as f:
        content = f.read()
        
    with open(backup_file_path, 'w') as f:
        f.write(content)
    
    # Fix the escaped triple-quoted docstring
    problematic_pattern = r'\\"\\\\"\\"\s*Generate a diff between two versions of an ontology\s*\\"\\\\"\\"\s*'
    
    if re.search(problematic_pattern, content):
        # Replace with a proper docstring
        updated_content = re.sub(
            problematic_pattern,
            '"""Generate a diff between two versions of an ontology"""\n        ',
            content
        )
        
        print("Fixed the docstring syntax error")
    else:
        # Alternative pattern to try
        alt_pattern = r'"\\"\\"\\"Generate a diff between two versions of an ontology\\"\\"\\""\s*'
        if re.search(alt_pattern, content):
            updated_content = re.sub(
                alt_pattern,
                '"""Generate a diff between two versions of an ontology"""\n        ',
                content
            )
            print("Fixed the docstring syntax error (alternative pattern)")
        else:
            # Direct replacement as a last resort
            updated_content = content.replace(
                '\"\"\"Generate a diff between two versions of an ontology\"\"\"',
                '"""Generate a diff between two versions of an ontology"""'
            )
            print("Fixed the docstring syntax error (direct replacement)")
    
    # Write the updated content back
    with open(routes_file_path, 'w') as f:
        f.write(updated_content)
    
    print(f"Successfully updated {routes_file_path} with fixed docstring")
    return True

if __name__ == "__main__":
    if fix_docstring_syntax():
        print("\nDocstring fix applied successfully!")
    else:
        print("\nFailed to apply docstring fix. Please check the error messages above.")
