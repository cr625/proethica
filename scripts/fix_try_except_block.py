#!/usr/bin/env python3
"""
Script to fix the try-except block structure in routes.py.
"""
import os
import sys

def fix_try_except_block():
    """
    Fix the try-except block structure in the diff endpoint.
    """
    # Path to the routes file
    routes_file_path = 'ontology_editor/api/routes.py'
    
    # Check if the file exists
    if not os.path.exists(routes_file_path):
        print(f"Error: {routes_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{routes_file_path}.try_except.bak'
    print(f"Creating backup of {routes_file_path} to {backup_file_path}")
    
    with open(routes_file_path, 'r') as f:
        lines = f.readlines()
        
    with open(backup_file_path, 'w') as f:
        f.writelines(lines)
    
    # Find the problematic try block
    try_line_num = None
    for i, line in enumerate(lines):
        if '@api_bp.route(\'/versions/<int:ontology_id>/diff\')' in line:
            # Look for the try statement in the next few lines
            for j in range(i, min(i + 10, len(lines))):
                if 'try:' in lines[j]:
                    try_line_num = j + 1  # 1-indexed line number
                    break
            break
    
    if try_line_num is None:
        print("Could not find the problematic try block")
        return False
    
    print(f"Found try statement at line {try_line_num}")
    
    # Now look for nested if statements without a proper except block
    except_found = False
    nested_if_start = None
    
    # Start from the try line and look for an except block or nested if
    for i in range(try_line_num, len(lines)):
        if 'except ' in lines[i]:
            except_found = True
            break
        
        # If we find a line with 'if' and the same indentation as 'try'
        # it means we have a nested if without an except
        if 'if ' in lines[i] and lines[i].startswith(' ' * 8):
            nested_if_start = i + 1  # 1-indexed line number
            break
    
    if except_found:
        print("Found a proper except block, no need to fix")
        return True
    
    if nested_if_start is None:
        print("Could not find a nested if statement or except block")
        return False
    
    print(f"Found nested if statement without except at line {nested_if_start}")
    
    # Reconstruct the function with a proper try-except block
    function_start = None
    function_end = None
    
    # Find the start of the function
    for i in range(try_line_num - 2, 0, -1):
        if 'def get_versions_diff' in lines[i]:
            function_start = i
            break
    
    # Find the end of the function - look for next def or route
    for i in range(try_line_num, len(lines)):
        if lines[i].strip().startswith('@api_bp.route') or lines[i].strip().startswith('def '):
            function_end = i
            break
    
    if function_start is None or function_end is None:
        print("Could not find the function boundaries")
        return False
    
    print(f"Function boundaries: {function_start+1} to {function_end}")
    
    # Extract the function body without the try block
    function_header = lines[function_start:try_line_num - 1]
    try_block_content = lines[try_line_num:nested_if_start - 1]
    nested_if_content = lines[nested_if_start - 1:function_end]
    
    # Recreate the function with a proper try-except structure
    new_function = []
    new_function.extend(function_header)
    new_function.append('        try:\n')
    
    # For the try block, we need to keep the initial comments and variable declarations
    for line in try_block_content:
        new_function.append(line)
    
    # Add the nested if contents within the try block
    for line in nested_if_content:
        new_function.append(line)
    
    # Add the except block
    new_function.append('        except Exception as e:\n')
    new_function.append('            current_app.logger.error(f"Error generating diff: {str(e)}")\n')
    new_function.append('            return jsonify({\'error\': f\'Failed to generate diff: {str(e)}\', \'details\': str(e)}), 500\n')
    
    # Update the file
    updated_lines = lines[:function_start] + new_function + lines[function_end:]
    
    with open(routes_file_path, 'w') as f:
        f.writelines(updated_lines)
    
    print(f"Successfully fixed try-except block structure")
    print("Try running the server now with './start_proethica.sh'")
    
    return True

if __name__ == "__main__":
    if fix_try_except_block():
        print("\nTry-except block fix applied successfully!")
    else:
        print("\nFailed to apply try-except block fix. Please check the error messages above.")
