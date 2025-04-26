#!/usr/bin/env python3
"""
Script to fix the indentation of the try block to match the docstring.
"""
import os
import sys

def fix_function_block():
    """
    Fix the indentation of the try block to match the docstring.
    """
    # Path to the routes file
    routes_file_path = 'ontology_editor/api/routes.py'
    
    # Check if the file exists
    if not os.path.exists(routes_file_path):
        print(f"Error: {routes_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{routes_file_path}.function_block.bak'
    print(f"Creating backup of {routes_file_path} to {backup_file_path}")
    
    with open(routes_file_path, 'r') as f:
        lines = f.readlines()
        
    with open(backup_file_path, 'w') as f:
        f.writelines(lines)
    
    # Check the docstring and try block lines
    doc_line_num = 299
    try_line_num = 300
    
    if len(lines) >= try_line_num:
        # Get the lines
        doc_line = lines[doc_line_num - 1]
        try_line = lines[try_line_num - 1]
        
        print(f"Original docstring line ({doc_line_num}): {doc_line}")
        print(f"Original try line ({try_line_num}): {try_line}")
        
        # Calculate the correct indentation for try block - should match docstring
        doc_indentation = len(doc_line) - len(doc_line.lstrip())
        
        # Check if try block needs indentation fixing
        if not try_line.startswith(' ' * doc_indentation):
            # Fix the try block indentation
            lines[try_line_num - 1] = ' ' * doc_indentation + try_line.lstrip()
            print(f"Fixed try line ({try_line_num}): {lines[try_line_num - 1]}")
            
            # Now fix all the subsequent lines in this function
            # Look for end of function or next top-level statement
            i = try_line_num + 1
            while i < len(lines):
                line = lines[i - 1]
                
                # Check if this line is blank or is the start of a new function/endpoint
                if (line.strip() == '' or
                    line.lstrip().startswith('@api_bp.route') or 
                    line.lstrip().startswith('def ')):
                    break
                
                # Fix indentation to be the same as the try line
                if line.strip():  # Skip empty lines
                    # Remove any existing indentation
                    stripped = line.lstrip()
                    # Add 4 more spaces than the docstring for the block content
                    lines[i - 1] = ' ' * (doc_indentation + 4) + stripped
                
                i += 1
            
            print(f"Fixed indentation for the function block from line {try_line_num} to {i-1}")
        else:
            print("Try block already has correct indentation")
            return True
    else:
        print(f"Error: File has less than {try_line_num} lines")
        return False
    
    # Write the fixed content back
    with open(routes_file_path, 'w') as f:
        f.writelines(lines)
    
    print(f"Successfully fixed function block indentation")
    print("Try running the server now with './start_proethica.sh'")
    
    return True

if __name__ == "__main__":
    if fix_function_block():
        print("\nFunction block indentation fix applied successfully!")
    else:
        print("\nFailed to apply function block indentation fix. Please check the error messages above.")
