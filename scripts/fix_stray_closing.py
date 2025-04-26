#!/usr/bin/env python
"""
Fix the stray closing bracket in editor.js after the initializeEditor function
"""
import os

def fix_stray_closing():
    """
    Remove the stray '});' that appears after the initializeEditor function
    """
    js_file_path = 'ontology_editor/static/js/editor.js'
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = 'ontology_editor/static/js/editor.js.stray_fix.bak'
    print(f"Creating backup of {js_file_path} to {backup_file_path}")
    with open(js_file_path, 'r') as f:
        original_content = f.read()
    
    with open(backup_file_path, 'w') as f:
        f.write(original_content)
    
    # Find and remove the stray '});' after the initializeEditor function
    lines = original_content.split('\n')
    fixed_lines = []
    
    # Flag to mark where we found the initializeEditor function
    in_init_function = False
    found_closing_brace = False
    skip_next_line = False
    
    for i, line in enumerate(lines):
        if not in_init_function and line.strip() == "function initializeEditor() {":
            in_init_function = True
            fixed_lines.append(line)
            continue
            
        if in_init_function and line.strip() == "}":
            in_init_function = False
            found_closing_brace = True
            fixed_lines.append(line)
            continue
            
        if found_closing_brace and line.strip() == "});":
            print(f"Found stray closing at line {i+1}: '{line}'")
            found_closing_brace = False
            # Skip this line
            continue
            
        fixed_lines.append(line)
    
    # Write the fixed content
    with open(js_file_path, 'w') as f:
        f.write('\n'.join(fixed_lines))
    
    print("Fixed stray closing bracket in editor.js")
    return True

if __name__ == "__main__":
    if fix_stray_closing():
        print("Successfully fixed stray closing bracket issue")
    else:
        print("Failed to fix stray closing bracket issue")
