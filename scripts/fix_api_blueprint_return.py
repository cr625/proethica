#!/usr/bin/env python3
"""
Script to fix the api routes function to properly return the blueprint.
"""
import os
import sys

def fix_api_blueprint_return():
    """
    Fix the create_api_routes function to properly return the blueprint.
    """
    # Path to the routes file
    routes_file_path = 'ontology_editor/api/routes.py'
    
    # Check if the file exists
    if not os.path.exists(routes_file_path):
        print(f"Error: {routes_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{routes_file_path}.missing_return.bak'
    print(f"Creating backup of {routes_file_path} to {backup_file_path}")
    
    with open(routes_file_path, 'r') as f:
        content = f.read()
        
    with open(backup_file_path, 'w') as f:
        f.write(content)
    
    # Check if there's a return statement for the blueprint
    if 'return api_bp' not in content:
        # Add a return statement at the end of the create_api_routes function
        
        # Find the function definition
        function_def_pos = content.find('def create_api_routes')
        if function_def_pos == -1:
            print("Could not find the create_api_routes function definition")
            return False
        
        # Find the end of the function, which is either the next function or the end of file
        next_func_pos = content.find('\ndef ', function_def_pos + 1)
        
        if next_func_pos != -1:
            # Found another function, insert before it
            # We need to go back to the last line of the previous function
            lines = content[:next_func_pos].split('\n')
            
            # Find the last non-blank line
            last_line_idx = len(lines) - 1
            while last_line_idx >= 0 and not lines[last_line_idx].strip():
                last_line_idx -= 1
                
            if last_line_idx >= 0:
                # Get the indentation of the first line in the function (should be 4 spaces)
                function_lines = [line for line in content.split('\n') if 'def create_api_routes' in line]
                if function_lines:
                    first_line = function_lines[0]
                    indentation = len(first_line) - len(first_line.lstrip())
                    indent = ' ' * indentation
                else:
                    indent = '    '  # Default indentation
                
                # Insert the return statement with proper indentation
                return_statement = f"{indent}return api_bp\n\n"
                
                modified_content = content[:next_func_pos]
                if not modified_content.endswith('\n\n'):
                    if modified_content.endswith('\n'):
                        return_statement = return_statement.lstrip('\n')
                    else:
                        return_statement = '\n' + return_statement
                
                modified_content += return_statement + content[next_func_pos:]
                
                with open(routes_file_path, 'w') as f:
                    f.write(modified_content)
                
                print("Added return statement at the end of the create_api_routes function")
                return True
            else:
                print("Could not find the last line of the function")
                return False
        else:
            # This is the last function, append to the end of the file
            indent = '    '  # Default indentation
            return_statement = f"\n{indent}return api_bp\n"
            
            modified_content = content + return_statement
            
            with open(routes_file_path, 'w') as f:
                f.write(modified_content)
            
            print("Added return statement at the end of the file")
            return True
    else:
        print("Return statement already exists in the create_api_routes function")
        return True

if __name__ == "__main__":
    if fix_api_blueprint_return():
        print("\nAPI blueprint return fix applied successfully!")
    else:
        print("\nFailed to apply API blueprint return fix. Please check the error messages above.")
