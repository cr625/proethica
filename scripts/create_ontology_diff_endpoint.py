#!/usr/bin/env python3
"""
Script to add a diff endpoint to the ontology editor API.
This endpoint will allow comparing different versions of an ontology.
"""
import os
import re
import sys
import difflib

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def add_diff_endpoint():
    """
    Add a new diff endpoint to the ontology editor API routes.
    """
    # Path to the routes file
    routes_file_path = 'ontology_editor/api/routes.py'
    
    # Check if the file exists
    if not os.path.exists(routes_file_path):
        print(f"Error: {routes_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{routes_file_path}.diff_endpoint.bak'
    print(f"Creating backup of {routes_file_path} to {backup_file_path}")
    
    with open(routes_file_path, 'r') as f:
        original_content = f.read()
        
    with open(backup_file_path, 'w') as f:
        f.write(original_content)
    
    # Parse the content to find where to add the new endpoint
    lines = original_content.split('\n')
    
    # Find the last API endpoint definition
    last_endpoint_idx = -1
    for i in range(len(lines) - 1, -1, -1):
        if '@api_bp.route' in lines[i]:
            last_endpoint_idx = i
            # Find the end of this function
            for j in range(i + 1, len(lines)):
                if lines[j].startswith('@api_bp.route') or lines[j].startswith('def '):
                    last_endpoint_idx = j - 1
                    break
            break
    
    if last_endpoint_idx == -1:
        print("Could not find the last API endpoint definition.")
        return False
    
    # Find the end of the last endpoint function
    for i in range(last_endpoint_idx + 1, len(lines)):
        if re.match(r'^@api_bp\.route|^def\s+|^#\s+Return the Blueprint|^return\s+api_bp', lines[i]):
            last_endpoint_idx = i - 1
            break
    
    # Create the new endpoint code
    new_endpoint = """
    @api_bp.route('/versions/<int:ontology_id>/diff')
    def get_versions_diff(ontology_id):
        \"\"\"Generate a diff between two versions of an ontology\"\"\"
        try:
            # Get query parameters
            from_version = request.args.get('from')
            to_version = request.args.get('to')
            format_type = request.args.get('format', 'unified')  # unified or split
            
            if not from_version:
                return jsonify({'error': 'Missing "from" parameter'}), 400
            
            # If to_version is not specified, compare with the current version
            if not to_version:
                # Get the current (latest) version
                latest_version = OntologyVersion.query.filter_by(
                    ontology_id=ontology_id
                ).order_by(OntologyVersion.version_number.desc()).first()
                
                if not latest_version:
                    return jsonify({'error': f'No versions found for ontology {ontology_id}'}), 404
                
                to_version = str(latest_version.version_number)
            
            # Get the content of both versions
            try:
                from_version_obj = OntologyVersion.query.filter_by(
                    ontology_id=ontology_id,
                    version_number=int(from_version)
                ).first_or_404()
                
                to_version_obj = OntologyVersion.query.filter_by(
                    ontology_id=ontology_id,
                    version_number=int(to_version)
                ).first_or_404()
            except ValueError:
                return jsonify({'error': 'Version numbers must be integers'}), 400
            
            # Get the content of both versions
            from_content = from_version_obj.content
            to_content = to_version_obj.content
            
            # Generate the diff
            from_lines = from_content.splitlines(keepends=True)
            to_lines = to_content.splitlines(keepends=True)
            
            if format_type == 'unified':
                diff = difflib.unified_diff(
                    from_lines, 
                    to_lines,
                    fromfile=f'Version {from_version}',
                    tofile=f'Version {to_version}',
                    lineterm=''
                )
                diff_text = ''.join(diff)
            else:  # HTML diff with side-by-side option for frontend
                diff = difflib.HtmlDiff()
                diff_text = diff.make_table(
                    from_lines,
                    to_lines,
                    fromdesc=f'Version {from_version}',
                    todesc=f'Version {to_version}',
                    context=True,
                    numlines=3
                )
            
            # Return the diff and metadata
            result = {
                'diff': diff_text,
                'format': format_type,
                'from_version': {
                    'number': from_version_obj.version_number,
                    'created_at': from_version_obj.created_at.isoformat() if from_version_obj.created_at else None,
                    'commit_message': from_version_obj.commit_message
                },
                'to_version': {
                    'number': to_version_obj.version_number,
                    'created_at': to_version_obj.created_at.isoformat() if to_version_obj.created_at else None,
                    'commit_message': to_version_obj.commit_message
                }
            }
            
            return jsonify(result)
        except Exception as e:
            current_app.logger.error(f"Error generating diff: {str(e)}")
            return jsonify({'error': f'Failed to generate diff', 'details': str(e)}), 500
    """
    
    # Insert the new endpoint after the last existing one
    new_lines = lines[:last_endpoint_idx + 1] + [new_endpoint] + lines[last_endpoint_idx + 1:]
    updated_content = '\n'.join(new_lines)
    
    # Write the updated content back
    with open(routes_file_path, 'w') as f:
        f.write(updated_content)
    
    print(f"Successfully added diff endpoint to {routes_file_path}")
    print("\nNew endpoint available at: GET /ontology-editor/api/versions/<int:ontology_id>/diff")
    print("Query parameters:")
    print("  - from: Source version number (required)")
    print("  - to: Target version number (optional, defaults to latest version)")
    print("  - format: 'unified' for text-based diff or 'split' for HTML table diff (default: 'unified')")
    
    return True

if __name__ == "__main__":
    if add_diff_endpoint():
        print("\nEndpoint added successfully!")
    else:
        print("\nFailed to add endpoint. Please check the error messages above.")
