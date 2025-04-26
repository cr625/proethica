#!/usr/bin/env python3
"""
Script to fix indentation issues in routes.py to align docstring and try statement.
"""
import os
import sys

def fix_indentation():
    """
    Fix indentation mismatch between docstring and try statement.
    """
    # Path to the routes file
    routes_file_path = 'ontology_editor/api/routes.py'
    
    # Check if the file exists
    if not os.path.exists(routes_file_path):
        print(f"Error: {routes_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{routes_file_path}.indentation.bak'
    print(f"Creating backup of {routes_file_path} to {backup_file_path}")
    
    with open(routes_file_path, 'r') as f:
        lines = f.readlines()
        
    with open(backup_file_path, 'w') as f:
        f.writelines(lines)
    
    # Check line at index 299 (line 300)
    if len(lines) >= 300 and lines[299].startswith('        try:'):
        # The try block has more indentation than the docstring
        # Fix the try block and subsequent lines
        print("Found indentation mismatch: docstring has 4 spaces, try block has 8 spaces")
        
        # Line 300 is the try statement
        line_num = 300
        try_line = lines[line_num - 1]
        print(f"Original try line ({line_num}): {try_line}")
        
        # Get the function body lines
        function_body = []
        i = line_num
        while i < len(lines):
            line = lines[i - 1]
            # Check if we've hit the next function or endpoint
            if line.lstrip().startswith('@api_bp.route') or line.lstrip().startswith('def '):
                if i > line_num:  # Make sure we're not at the current function
                    break
            function_body.append(line)
            i += 1
        
        # Adjust indentation levels to match docstring (should be 4 spaces)
        adjusted_body = []
        for line in function_body:
            if line.startswith('        '):  # 8 spaces
                adjusted_body.append(line[4:])  # Remove 4 spaces to get to 4 spaces
            else:
                adjusted_body.append(line)  # Keep other lines as is
        
        # Replace function body with adjusted indentation
        lines[line_num-1:i-1] = adjusted_body
        
        # Write the fixed content back
        with open(routes_file_path, 'w') as f:
            f.writelines(lines)
        
        print(f"Fixed indentation mismatch in line range {line_num}-{i-1}")
    else:
        print(f"No indentation mismatch found in line 300 or file has less than {300} lines")
        return False
    
    print("Try running the server now with './start_proethica.sh'")
    return True

if __name__ == "__main__":
    if fix_indentation():
        print("\nIndentation fix applied successfully!")
    else:
        print("\nFailed to apply indentation fix. Please check the error messages above.")
