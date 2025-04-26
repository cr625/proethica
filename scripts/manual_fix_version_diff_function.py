#!/usr/bin/env python3
"""
Script to manually rewrite the entire get_versions_diff function in routes.py
to fix the syntax and structure issues.
"""
import os
import sys
import re

def fix_versions_diff_function():
    """
    Manually rewrite the entire get_versions_diff function with proper structure.
    """
    # Path to the routes file
    routes_file_path = 'ontology_editor/api/routes.py'
    
    # Check if the file exists
    if not os.path.exists(routes_file_path):
        print(f"Error: {routes_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{routes_file_path}.full_rewrite.bak'
    print(f"Creating backup of {routes_file_path} to {backup_file_path}")
    
    with open(routes_file_path, 'r') as f:
        content = f.read()
        
    with open(backup_file_path, 'w') as f:
        f.write(content)
    
    # Define the pattern to match the entire get_versions_diff function
    pattern = r'([ \t]*)@api_bp\.route\([\'\"]\/versions\/<int:ontology_id>\/diff[\'\"]\)\s*\n([ \t]*)def get_versions_diff\(ontology_id\):[\s\S]*?(?=\n\s*@api_bp\.route|\n\s*def |$)'
    
    match = re.search(pattern, content)
    if not match:
        print("Could not find the get_versions_diff function")
        return False
    
    # Extract indentation
    route_indent = match.group(1)
    function_indent = match.group(2)
    body_indent = function_indent + "    "  # 4 spaces more than function def
    
    print(f"Found indentation: route={len(route_indent)}, function={len(function_indent)}, body={len(body_indent)}")
    
    # Create a corrected implementation with proper structure
    corrected_function = f"""
{route_indent}@api_bp.route('/versions/<int:ontology_id>/diff')
{function_indent}def get_versions_diff(ontology_id):
{body_indent}\"\"\"Generate a diff between two versions of an ontology\"\"\"
{body_indent}try:
{body_indent}    # Get query parameters
{body_indent}    from_version = request.args.get('from')
{body_indent}    to_version = request.args.get('to')
{body_indent}    format_type = request.args.get('format', 'unified')  # unified or split
{body_indent}    
{body_indent}    if not from_version:
{body_indent}        return jsonify({{'error': 'Missing "from" parameter'}}), 400
{body_indent}    
{body_indent}    # If to_version is not specified, compare with the current version
{body_indent}    if not to_version:
{body_indent}        # Get the current (latest) version
{body_indent}        latest_version = OntologyVersion.query.filter_by(
{body_indent}            ontology_id=ontology_id
{body_indent}        ).order_by(OntologyVersion.version_number.desc()).first()
{body_indent}        
{body_indent}        if not latest_version:
{body_indent}            return jsonify({{'error': f'No versions found for ontology {{ontology_id}}'}}), 404
{body_indent}        
{body_indent}        to_version = str(latest_version.version_number)
{body_indent}    
{body_indent}    # Check if versions are the same
{body_indent}    if from_version == to_version:
{body_indent}        return jsonify({{
{body_indent}            'diff': 'No differences (same version)',
{body_indent}            'format': format_type,
{body_indent}            'from_version': {{
{body_indent}                'number': int(from_version),
{body_indent}                'created_at': None,
{body_indent}                'commit_message': None
{body_indent}            }},
{body_indent}            'to_version': {{
{body_indent}                'number': int(to_version),
{body_indent}                'created_at': None,
{body_indent}                'commit_message': None
{body_indent}            }}
{body_indent}        }})
{body_indent}    
{body_indent}    try:
{body_indent}        # Get the content of both versions
{body_indent}        from_version_obj = OntologyVersion.query.filter_by(
{body_indent}            ontology_id=ontology_id,
{body_indent}            version_number=int(from_version)
{body_indent}        ).first()
{body_indent}        
{body_indent}        to_version_obj = OntologyVersion.query.filter_by(
{body_indent}            ontology_id=ontology_id,
{body_indent}            version_number=int(to_version)
{body_indent}        ).first()
{body_indent}        
{body_indent}        if not from_version_obj:
{body_indent}            return jsonify({{'error': f'Version {{from_version}} not found for ontology {{ontology_id}}'}}), 404
{body_indent}        
{body_indent}        if not to_version_obj:
{body_indent}            return jsonify({{'error': f'Version {{to_version}} not found for ontology {{ontology_id}}'}}), 404
{body_indent}        
{body_indent}        # Get the content of both versions
{body_indent}        from_content = from_version_obj.content
{body_indent}        to_content = to_version_obj.content
{body_indent}        
{body_indent}        # Generate the diff
{body_indent}        import difflib
{body_indent}        from_lines = from_content.splitlines(keepends=True)
{body_indent}        to_lines = to_content.splitlines(keepends=True)
{body_indent}        
{body_indent}        if format_type == 'unified':
{body_indent}            diff = difflib.unified_diff(
{body_indent}                from_lines, 
{body_indent}                to_lines,
{body_indent}                fromfile=f'Version {{from_version}}',
{body_indent}                tofile=f'Version {{to_version}}',
{body_indent}                lineterm=''
{body_indent}            )
{body_indent}            diff_text = ''.join(list(diff))
{body_indent}        else:  # HTML diff with side-by-side option for frontend
{body_indent}            diff = difflib.HtmlDiff()
{body_indent}            diff_text = diff.make_table(
{body_indent}                from_lines,
{body_indent}                to_lines,
{body_indent}                fromdesc=f'Version {{from_version}}',
{body_indent}                todesc=f'Version {{to_version}}',
{body_indent}                context=True,
{body_indent}                numlines=3
{body_indent}            )
{body_indent}        
{body_indent}        # Return the diff and metadata
{body_indent}        result = {{
{body_indent}            'diff': diff_text,
{body_indent}            'format': format_type,
{body_indent}            'from_version': {{
{body_indent}                'number': from_version_obj.version_number,
{body_indent}                'created_at': from_version_obj.created_at.isoformat() if from_version_obj.created_at else None,
{body_indent}                'commit_message': from_version_obj.commit_message
{body_indent}            }},
{body_indent}            'to_version': {{
{body_indent}                'number': to_version_obj.version_number,
{body_indent}                'created_at': to_version_obj.created_at.isoformat() if to_version_obj.created_at else None,
{body_indent}                'commit_message': to_version_obj.commit_message
{body_indent}            }}
{body_indent}        }}
{body_indent}        
{body_indent}        return jsonify(result)
{body_indent}    except ValueError:
{body_indent}        return jsonify({{'error': 'Version numbers must be integers'}}), 400
{body_indent}except Exception as e:
{body_indent}    current_app.logger.error(f"Error generating diff: {{str(e)}}")
{body_indent}    return jsonify({{'error': f'Failed to generate diff: {{str(e)}}', 'details': str(e)}}), 500
"""

    # Replace the function in the content
    updated_content = re.sub(pattern, corrected_function, content)
    
    # Write the modified content back to the file
    with open(routes_file_path, 'w') as f:
        f.write(updated_content)
    
    print("Successfully replaced the get_versions_diff function with a corrected implementation")
    print("Try running the server now with './start_proethica.sh'")
    
    return True

if __name__ == "__main__":
    if fix_versions_diff_function():
        print("\nFunction rewrite applied successfully!")
    else:
        print("\nFailed to rewrite function. Please check the error messages above.")
