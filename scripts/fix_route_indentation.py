#!/usr/bin/env python3
"""
Script to fix the indentation of the route definition in routes.py
"""
import os
import sys

def fix_route_indentation():
    """
    Fix the indentation of the @api_bp.route and def line to match the rest.
    """
    # Path to the routes file
    routes_file_path = 'ontology_editor/api/routes.py'
    
    # Check if the file exists
    if not os.path.exists(routes_file_path):
        print(f"Error: {routes_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{routes_file_path}.route_fix.bak'
    print(f"Creating backup of {routes_file_path} to {backup_file_path}")
    
    with open(routes_file_path, 'r') as f:
        lines = f.readlines()
        
    with open(backup_file_path, 'w') as f:
        f.writelines(lines)
    
    # Check the api route definition and function definition lines
    route_line_num = 297
    def_line_num = 298
    doc_line_num = 299
    
    if len(lines) >= route_line_num:
        # Get the lines
        route_line = lines[route_line_num - 1]
        def_line = lines[def_line_num - 1]
        doc_line = lines[doc_line_num - 1]
        
        print(f"Original route line ({route_line_num}): {route_line}")
        print(f"Original def line ({def_line_num}): {def_line}")
        print(f"Original docstring line ({doc_line_num}): {doc_line}")
        
        # Check if route line starts with @api_bp.route but without proper indentation
        if route_line.strip().startswith('@api_bp.route'):
            # Count spaces at the beginning of doc_line
            doc_indentation = len(doc_line) - len(doc_line.lstrip())
            
            # Ensure route line and def line have proper indentation
            if not route_line.startswith(' ' * doc_indentation):
                # Add proper indentation to the route and def lines
                lines[route_line_num - 1] = ' ' * doc_indentation + route_line.lstrip()
                lines[def_line_num - 1] = ' ' * doc_indentation + def_line.lstrip()
                print(f"Fixed route line ({route_line_num}): {lines[route_line_num - 1]}")
                print(f"Fixed def line ({def_line_num}): {lines[def_line_num - 1]}")
        else:
            print("Route line doesn't start with @api_bp.route or already has proper indentation")
            return False
    else:
        print(f"Error: File has less than {route_line_num} lines")
        return False
    
    # Write the fixed content back
    with open(routes_file_path, 'w') as f:
        f.writelines(lines)
    
    print(f"Successfully fixed route and function definition indentation")
    print("Try running the server now with './start_proethica.sh'")
    
    return True

if __name__ == "__main__":
    if fix_route_indentation():
        print("\nRoute indentation fix applied successfully!")
    else:
        print("\nFailed to apply route indentation fix. Please check the error messages above.")
