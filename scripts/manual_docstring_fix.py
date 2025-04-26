#!/usr/bin/env python3
"""
Script to manually fix the docstring syntax error in routes.py
with a direct line-by-line replacement approach.
"""
import os
import sys

def fix_docstring_manually():
    """
    Use a direct line-by-line approach to fix the docstring.
    """
    # Path to the routes file
    routes_file_path = 'ontology_editor/api/routes.py'
    
    # Check if the file exists
    if not os.path.exists(routes_file_path):
        print(f"Error: {routes_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{routes_file_path}.manual_fix.bak'
    print(f"Creating backup of {routes_file_path} to {backup_file_path}")
    
    with open(routes_file_path, 'r') as f:
        lines = f.readlines()
        
    with open(backup_file_path, 'w') as f:
        f.writelines(lines)
    
    # Find the problematic line (line 299)
    line_num = 299
    if len(lines) >= line_num:
        # Get the problematic line
        problem_line = lines[line_num - 1]  # Python is 0-indexed but line numbers are 1-indexed
        print(f"Original problematic line ({line_num}): {problem_line}")
        
        # Replace with a clean docstring
        lines[line_num - 1] = '    """Generate a diff between two versions of an ontology"""\n'
        print(f"Fixed line ({line_num}): {lines[line_num - 1]}")
    else:
        print(f"Error: File has less than {line_num} lines")
        return False
    
    # Write the fixed content back
    with open(routes_file_path, 'w') as f:
        f.writelines(lines)
    
    print(f"Successfully fixed docstring on line {line_num}")
    print("Try running the server now with './start_proethica.sh'")
    
    return True

if __name__ == "__main__":
    if fix_docstring_manually():
        print("\nManual docstring fix applied successfully!")
    else:
        print("\nFailed to apply manual docstring fix. Please check the error messages above.")
