#!/usr/bin/env python3
"""
Script to fix the docstring indentation in routes.py.
"""
import os
import sys

def fix_docstring_indentation():
    """
    Fix the docstring indentation to match the function definition.
    """
    # Path to the routes file
    routes_file_path = 'ontology_editor/api/routes.py'
    
    # Check if the file exists
    if not os.path.exists(routes_file_path):
        print(f"Error: {routes_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{routes_file_path}.docstring_indent.bak'
    print(f"Creating backup of {routes_file_path} to {backup_file_path}")
    
    with open(routes_file_path, 'r') as f:
        lines = f.readlines()
        
    with open(backup_file_path, 'w') as f:
        f.writelines(lines)
    
    # Check the function definition and docstring lines
    def_line_num = 298
    doc_line_num = 299
    
    if len(lines) >= doc_line_num:
        # Get the lines
        def_line = lines[def_line_num - 1]
        doc_line = lines[doc_line_num - 1]
        
        print(f"Original function def ({def_line_num}): {def_line}")
        print(f"Original docstring line ({doc_line_num}): {doc_line}")
        
        # Calculate the correct indentation for docstring
        def_indentation = len(def_line) - len(def_line.lstrip())
        doc_indentation = len(doc_line) - len(doc_line.lstrip())
        
        # Docstring should be indented 4 more spaces than function definition
        correct_doc_indentation = def_indentation + 4
        
        # Check if docstring needs indentation fixing
        if doc_indentation != correct_doc_indentation:
            # Fix the docstring indentation
            lines[doc_line_num - 1] = ' ' * correct_doc_indentation + doc_line.strip() + '\n'
            print(f"Fixed docstring line ({doc_line_num}): {lines[doc_line_num - 1]}")
        else:
            print("Docstring already has correct indentation")
            return True
    else:
        print(f"Error: File has less than {doc_line_num} lines")
        return False
    
    # Write the fixed content back
    with open(routes_file_path, 'w') as f:
        f.writelines(lines)
    
    print(f"Successfully fixed docstring indentation")
    print("Try running the server now with './start_proethica.sh'")
    
    return True

if __name__ == "__main__":
    if fix_docstring_indentation():
        print("\nDocstring indentation fix applied successfully!")
    else:
        print("\nFailed to apply docstring indentation fix. Please check the error messages above.")
