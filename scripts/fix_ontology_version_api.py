#!/usr/bin/env python
"""
Fix for the ontology version API to support loading versions by version number
rather than just by ID. This fixes the issue where the frontend is trying to
load versions by their version number but the API is expecting version IDs.
"""
import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.models.ontology_version import OntologyVersion
from flask import jsonify, Blueprint, abort

def modify_api_routes():
    """
    Create a patched version of the routes.py file that includes a
    function to get a version by version number rather than ID.
    """
    # Check if the original file exists
    routes_file_path = 'ontology_editor/api/routes.py'
    if not os.path.exists(routes_file_path):
        print(f"Error: {routes_file_path} not found")
        return False
    
    # Backup the original file if backup doesn't already exist
    backup_file_path = 'ontology_editor/api/routes.py.version_api.bak'
    if not os.path.exists(backup_file_path):
        print(f"Creating backup of {routes_file_path} to {backup_file_path}")
        with open(routes_file_path, 'r') as f:
            original_content = f.read()
        
        with open(backup_file_path, 'w') as f:
            f.write(original_content)
    
    # Read the current file
    with open(routes_file_path, 'r') as f:
        content = f.read()
    
    # Find the location of the get_version function
    get_version_func_index = content.find("@api_bp.route('/versions/<int:version_id>')")
    if get_version_func_index == -1:
        print("Error: Could not find get_version function in routes.py")
        return False
    
    # Find the end of the function - look for the next route or function definition
    # This is a bit tricky but we'll look for the next @api_bp.route or def
    next_func_index = content.find("@api_bp.route", get_version_func_index + 1)
    if next_func_index == -1:
        # Try looking for the next function definition
        next_func_index = content.find("\n    def ", get_version_func_index + 1)
    
    # If we still can't find the end, use a reasonable approximation
    if next_func_index == -1:
        # Find the end of the function by looking for indented lines
        lines = content[get_version_func_index:].split('\n')
        function_lines = []
        for i, line in enumerate(lines):
            if i == 0 or (line.startswith('    ') and not line.startswith('        ')):
                function_lines.append(line)
            elif line.strip() == '' or line.startswith('@') or line.startswith('def '):
                break
        
        # Get the index of the end of the function
        function_text = '\n'.join(function_lines)
        next_func_index = get_version_func_index + len(function_text)
    
    # Insert the new function after the get_version function
    new_function = """
    @api_bp.route('/versions/<int:ontology_id>/<int:version_number>')
    def get_version_by_number(ontology_id, version_number):
        \"\"\"Get a specific version by ontology ID and version number\"\"\"
        try:
            version = OntologyVersion.query.filter_by(
                ontology_id=ontology_id,
                version_number=version_number
            ).first_or_404()
            
            # Get the version details
            result = version.to_dict()
            
            # Include the content
            result['content'] = version.content
            
            return jsonify(result)
        except Exception as e:
            current_app.logger.error(f"Error fetching version {ontology_id}/{version_number}: {str(e)}")
            return jsonify({'error': f'Failed to fetch version {ontology_id}/{version_number}', 'details': str(e)}), 500
    """
    
    # Insert the new function
    modified_content = content[:next_func_index] + new_function + content[next_func_index:]
    
    # Update the JavaScript editor.js file to use the new API endpoint
    js_file_path = 'ontology_editor/static/js/editor.js'
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Backup the original JavaScript file if backup doesn't already exist
    js_backup_file_path = 'ontology_editor/static/js/editor.js.version_api.bak'
    if not os.path.exists(js_backup_file_path):
        print(f"Creating backup of {js_file_path} to {js_backup_file_path}")
        with open(js_file_path, 'r') as f:
            js_original_content = f.read()
        
        with open(js_backup_file_path, 'w') as f:
            f.write(js_original_content)
    
    # Read the current JavaScript file
    with open(js_file_path, 'r') as f:
        js_content = f.read()
    
    # Find the loadVersion function
    load_version_func_index = js_content.find("function loadVersion(versionId) {")
    if load_version_func_index == -1:
        print("Error: Could not find loadVersion function in editor.js")
        return False
    
    # Find the fetch call within that function
    fetch_index = js_content.find("fetch(`/ontology-editor/api/versions/${versionId}`)", load_version_func_index)
    if fetch_index == -1:
        print("Error: Could not find fetch call in loadVersion function")
        return False
    
    # Replace the fetch call with one that uses the ontology ID and version number
    modified_js_content = js_content.replace(
        "fetch(`/ontology-editor/api/versions/${versionId}`)",
        "fetch(`/ontology-editor/api/versions/${currentOntologyId}/${versionId}`)"
    )
    
    # Write modified files
    with open(routes_file_path, 'w') as f:
        f.write(modified_content)
    
    with open(js_file_path, 'w') as f:
        f.write(modified_js_content)
    
    print("Successfully modified API routes and JavaScript to support loading versions by version number")
    return True

if __name__ == "__main__":
    if modify_api_routes():
        print("Fix applied successfully")
    else:
        print("Failed to apply fix")
