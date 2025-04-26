#!/usr/bin/env python3
"""
Script to fix issues with the ontology diff API endpoint.
"""
import os
import re
import sys

def fix_diff_endpoint():
    """
    Fix issues with the diff endpoint in routes.py.
    """
    # Path to the routes file
    routes_file_path = 'ontology_editor/api/routes.py'
    
    # Check if the file exists
    if not os.path.exists(routes_file_path):
        print(f"Error: {routes_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{routes_file_path}.diff_fix.bak'
    print(f"Creating backup of {routes_file_path} to {backup_file_path}")
    
    with open(routes_file_path, 'r') as f:
        original_content = f.read()
        
    with open(backup_file_path, 'w') as f:
        f.write(original_content)
    
    # Check for missing imports and add them if needed
    updated_content = original_content
    
    # Ensure we have the "request" import from flask
    if "from flask import Blueprint, request, jsonify, current_app" not in updated_content:
        updated_content = updated_content.replace(
            "from flask import Blueprint, jsonify, current_app",
            "from flask import Blueprint, request, jsonify, current_app"
        )
        print("Added missing 'request' import from flask")
    
    # Fix the diff endpoint implementation
    diff_endpoint_pattern = re.compile(r'(@api_bp\.route\(\'/versions/<int:ontology_id>/diff\'\)\s*def get_versions_diff\(ontology_id\):.*?)return jsonify\(result\)', re.DOTALL)
    
    if diff_endpoint_pattern.search(updated_content):
        # Fix implementation to handle:
        # 1. Same version comparison
        # 2. Missing request import
        # 3. Proper error handling
        updated_endpoint = r"""
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
            
            # Check if versions are the same
            if from_version == to_version:
                return jsonify({
                    'diff': 'No differences (same version)',
                    'format': format_type,
                    'from_version': {
                        'number': int(from_version),
                        'created_at': None,
                        'commit_message': None
                    },
                    'to_version': {
                        'number': int(to_version),
                        'created_at': None,
                        'commit_message': None
                    }
                })
            
            try:
                # Get the content of both versions
                from_version_obj = OntologyVersion.query.filter_by(
                    ontology_id=ontology_id,
                    version_number=int(from_version)
                ).first()
                
                to_version_obj = OntologyVersion.query.filter_by(
                    ontology_id=ontology_id,
                    version_number=int(to_version)
                ).first()
                
                if not from_version_obj:
                    return jsonify({'error': f'Version {from_version} not found for ontology {ontology_id}'}), 404
                
                if not to_version_obj:
                    return jsonify({'error': f'Version {to_version} not found for ontology {ontology_id}'}), 404
                
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
                    diff_text = ''.join(list(diff))
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
            except ValueError:
                return jsonify({'error': 'Version numbers must be integers'}), 400
        except Exception as e:
            current_app.logger.error(f"Error generating diff: {str(e)}")
            return jsonify({'error': f'Failed to generate diff: {str(e)}', 'details': str(e)}), 500
    """
        
        # Find the start and end of the diff function
        diff_start = re.search(r'@api_bp\.route\(\'/versions/<int:ontology_id>/diff\'\)', updated_content)
        if not diff_start:
            print("Could not find the start of the diff endpoint function.")
            return False
        
        # Find the next endpoint or the end of the file
        next_endpoint = re.search(r'@api_bp\.route', updated_content[diff_start.end():])
        if next_endpoint:
            diff_end = diff_start.end() + next_endpoint.start()
        else:
            # Find the end of the function using indentation
            lines = updated_content[diff_start.end():].split('\n')
            for i, line in enumerate(lines):
                if line.startswith('    @') or line.startswith('def ') or line.startswith('# Return'):
                    diff_end = diff_start.end() + sum(len(l) + 1 for l in lines[:i])
                    break
            else:
                diff_end = len(updated_content)
        
        # Replace the function
        updated_content = updated_content[:diff_start.start()] + updated_endpoint + updated_content[diff_end:]
        print("Fixed the diff endpoint implementation")
    else:
        print("Could not find the diff endpoint function. It may have been renamed or removed.")
        return False
    
    # Write the updated content back
    with open(routes_file_path, 'w') as f:
        f.write(updated_content)
    
    print(f"Successfully updated {routes_file_path} with fixed diff endpoint")
    print("\nKey fixes:")
    print("1. Added check for comparing same version")
    print("2. Improved error handling")
    print("3. Made sure 'request' is imported")
    print("4. Fixed handling of version objects")
    print("5. Converted diff generator output to a list before joining")
    
    return True

if __name__ == "__main__":
    if fix_diff_endpoint():
        print("\nDiff endpoint fix applied successfully!")
    else:
        print("\nFailed to apply fix. Please check the error messages above.")
