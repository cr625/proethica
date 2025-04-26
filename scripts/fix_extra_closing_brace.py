#!/usr/bin/env python
"""
Fix a syntax error in editor.js caused by an extra closing parenthesis and brace.
"""
import os

def fix_extra_brace():
    """
    Fix the extra "}); that appears before the loadVersion function.
    """
    print("Fixing extra closing brace in ontology_editor/static/js/editor.js...")
    
    js_file_path = 'ontology_editor/static/js/editor.js'
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = 'ontology_editor/static/js/editor.js.brace_fix.bak'
    print(f"Creating backup of {js_file_path} to {backup_file_path}")
    with open(js_file_path, 'r') as f:
        original_content = f.read()
    
    with open(backup_file_path, 'w') as f:
        f.write(original_content)
    
    # Find and remove the problematic line
    # The issue is an extra "}); that's between the version list click handler
    # and the loadVersion function
    lines = original_content.split('\n')
    
    # Looking for the pattern where we have the extra closing brace
    # before the loadVersion function
    fixed_lines = []
    skip_next = False
    
    for i, line in enumerate(lines):
        if skip_next:
            skip_next = False
            continue
            
        # Check if this is the problematic line
        if line.strip() == "});":
            # Look ahead to see if next lines seem to be the loadVersion function
            if i + 1 < len(lines) and lines[i+1].strip() == "":
                if i + 2 < len(lines) and "Load a specific version into the editor" in lines[i+2]:
                    print(f"Found problematic line {i+1}: '{line}'")
                    skip_next = False  # Don't skip the blank line
                    continue  # Skip only this closing brace line
        
        fixed_lines.append(line)
    
    # Write the fixed content back to the file
    with open(js_file_path, 'w') as f:
        f.write('\n'.join(fixed_lines))
    
    print("Fixed extra closing brace in editor.js")
    return True

if __name__ == "__main__":
    if fix_extra_brace():
        print("Successfully fixed extra closing brace in editor.js")
    else:
        print("Failed to fix editor.js")
