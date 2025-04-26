#!/usr/bin/env python
"""
Fix the extra closing bracket and parenthesis in editor.js that's causing a syntax error.
This is a simple targeted fix that just removes the problematic '});' at line 465.
"""
import os
import re

def fix_syntax_error():
    """
    Fix the extra closing bracket and parenthesis in editor.js.
    """
    js_file_path = 'ontology_editor/static/js/editor.js'
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create a backup with a clear name
    backup_file_path = 'ontology_editor/static/js/editor.js.before_syntax_fix.bak'
    print(f"Creating backup of {js_file_path} to {backup_file_path}")
    with open(js_file_path, 'r') as f:
        original_content = f.read()
    
    with open(backup_file_path, 'w') as f:
        f.write(original_content)
    
    # Simple pattern to find the problematic closing '});'
    pattern = re.compile(r'(document\.querySelectorAll\(\'#versionList li\'\)\.forEach\(item => \{\n.*?}\);\s*\n\s*}\);)\s*\n\s*}\);\s*\n\s*}', re.DOTALL)
    
    # Check if the pattern exists
    match = pattern.search(original_content)
    if not match:
        print("Could not find the problematic pattern. Using manual line approach...")
        # Fallback to a manual line approach if regex doesn't match
        lines = original_content.split('\n')
        fixed_lines = []
        skip_next = False
        
        for i, line in enumerate(lines):
            if skip_next:
                skip_next = False
                continue
                
            # Look for the exact line with the extra '});'
            # This is after the version list click handlers and before loadVersion function
            if line.strip() == "});":
                next_multiple_lines = "\n".join(lines[i+1:i+5])
                if "Load a specific version into the editor" in next_multiple_lines:
                    print(f"Found problematic line at line {i+1}: '{line}'")
                    continue  # Skip this line
            
            fixed_lines.append(line)
        
        # Write the fixed content
        with open(js_file_path, 'w') as f:
            f.write('\n'.join(fixed_lines))
        
        print("Fixed the syntax error by removing the extra '});'")
        return True
    else:
        # Replace the matched content with the correct version
        fixed_content = pattern.sub(r'\1\n}', original_content)
        
        # Write the fixed content
        with open(js_file_path, 'w') as f:
            f.write(fixed_content)
        
        print("Fixed the syntax error by removing the extra '});'")
        return True

if __name__ == "__main__":
    if fix_syntax_error():
        print("Successfully fixed syntax error in editor.js")
    else:
        print("Failed to fix syntax error")
