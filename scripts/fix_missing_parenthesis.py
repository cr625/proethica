#!/usr/bin/env python
"""
Fix a missing closing parenthesis in the editor.js file
"""
import os

def fix_missing_parenthesis():
    """
    Fix the missing closing parenthesis in the editor.getSession().on('change', function() {}) call
    """
    js_file_path = 'ontology_editor/static/js/editor.js'
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = 'ontology_editor/static/js/editor.js.parenthesis.bak'
    print(f"Creating backup of {js_file_path} to {backup_file_path}")
    with open(js_file_path, 'r') as f:
        original_content = f.read()
    
    with open(backup_file_path, 'w') as f:
        f.write(original_content)
    
    # Fix the getSession().on('change', function() {}) call
    lines = original_content.split('\n')
    fixed_lines = []
    
    # Flag to mark where we are inside the change function
    in_change_function = False
    
    for i, line in enumerate(lines):
        if not in_change_function and "editor.getSession().on('change', function()" in line:
            in_change_function = True
            fixed_lines.append(line)
            continue
            
        if in_change_function and line.strip() == "}":
            # This is the end of the change function, but it's missing the closing parenthesis
            fixed_lines.append("    });")  # Properly closed function with parenthesis
            in_change_function = False
            continue
            
        fixed_lines.append(line)
    
    # Write the fixed content
    with open(js_file_path, 'w') as f:
        f.write('\n'.join(fixed_lines))
    
    print("Fixed missing closing parenthesis in editor.js")
    return True

if __name__ == "__main__":
    if fix_missing_parenthesis():
        print("Successfully fixed missing parenthesis issue")
    else:
        print("Failed to fix missing parenthesis issue")
