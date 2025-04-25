#!/usr/bin/env python3
"""
Script to update the ontology editor with improved URL parameter handling and version display.
This script replaces the existing editor.js with the improved version and updates the HTML template
to include the new version dropdown in the toolbar.
"""
import os
import sys
import shutil
from datetime import datetime
import re

def backup_file(file_path):
    """Create a backup of a file before modifying it"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"{file_path}.{timestamp}.bak"
    
    if os.path.exists(file_path):
        print(f"Creating backup: {backup_path}")
        shutil.copy2(file_path, backup_path)
        return True
    else:
        print(f"Warning: File {file_path} does not exist, cannot create backup")
        return False

def update_editor_js():
    """Replace the existing editor.js with our improved version"""
    source_file = "ontology_editor/static/js/editor_improvements.js"
    target_file = "ontology_editor/static/js/editor.js"
    
    if not os.path.exists(source_file):
        print(f"Error: Source file {source_file} not found")
        return False
    
    # Backup the original file
    if os.path.exists(target_file):
        backup_file(target_file)
    
    # Copy the improved JS file
    print(f"Updating {target_file} with improvements")
    shutil.copy2(source_file, target_file)
    return True

def update_editor_html():
    """Update the editor.html template to add CSS for the improved version display"""
    template_file = "ontology_editor/templates/editor.html"
    
    if not os.path.exists(template_file):
        print(f"Error: Template file {template_file} not found")
        return False
    
    # Backup the original file
    backup_file(template_file)
    
    # Read the template file
    with open(template_file, 'r') as f:
        content = f.read()
    
    # Add CSS for version display improvements
    css_additions = """
    <style>
        /* Improved version display styles */
        .version-dropdown {
            margin-left: 10px;
        }
        .version-dropdown-item small {
            max-width: 200px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }
        .active-ontology {
            background-color: #e9f5ff;
            border-left: 3px solid #0d6efd;
        }
        .full-width-mode {
            max-width: 100%;
            padding-left: 30px;
            padding-right: 30px;
        }
        .loading-overlay {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(255, 255, 255, 0.8);
            display: flex;
            align-items: center;
            justify-content: center;
            flex-direction: column;
            z-index: 1000;
        }
        .validation-success {
            color: #198754;
        }
        .validation-warning {
            color: #fd7e14;
        }
        .validation-error {
            color: #dc3545;
        }
        .validation-suggestion {
            color: #0d6efd;
        }
        /* Sidebar improvements */
        .version-info {
            display: flex;
            align-items: center;
            gap: 6px;
            flex-wrap: wrap;
        }
        .version-number {
            font-weight: bold;
        }
        .version-date {
            font-size: 0.8rem;
            color: #6c757d;
        }
        .version-message {
            margin-top: 5px;
            font-size: 0.85rem;
            color: #495057;
            font-style: italic;
        }
    </style>
    """
    
    # Find the position to insert the CSS (after the existing CSS links but before the script tags)
    insertion_point = content.find('<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>')
    
    if insertion_point == -1:
        # Alternative: insert after the last <link> tag
        match = re.search(r'<link[^>]*>[^<]*(?:<\/link>)?', content)
        if match:
            insertion_point = match.end()
        else:
            # Last resort: insert at the end of the head section
            insertion_point = content.find('</head>')
    
    if insertion_point == -1:
        print("Error: Could not find a suitable insertion point for CSS")
        return False
    
    # Insert the CSS
    new_content = content[:insertion_point] + css_additions + content[insertion_point:]
    
    # Write the updated template
    with open(template_file, 'w') as f:
        f.write(new_content)
    
    print(f"Updated {template_file} with CSS improvements")
    return True

def update_api_routes():
    """Create a version-info endpoint in the API routes"""
    routes_file = "ontology_editor/api/routes.py"
    
    if not os.path.exists(routes_file):
        print(f"Error: API routes file {routes_file} not found")
        return False
    
    # Backup the original file
    backup_file(routes_file)
    
    # Read the routes file
    with open(routes_file, 'r') as f:
        content = f.read()
    
    # Check if the version-info endpoint already exists
    if 'version-info' in content:
        print("version-info endpoint appears to already exist, skipping")
        return True
    
    # Find a good insertion point (after the existing versions endpoint)
    versions_endpoint = re.search(r'@api_bp\.route\([\'"]\/versions\/.*?def get_version\(.*?\):', content, re.DOTALL)
    
    if not versions_endpoint:
        print("Error: Could not find the versions endpoint to add our new endpoint after")
        return False
    
    # Find the end of the function
    function_body = content[versions_endpoint.end():]
    function_match = re.search(r'(\s+return jsonify\(.*?\))', function_body)
    
    if not function_match:
        print("Error: Could not determine where to insert the new endpoint")
        return False
    
    insertion_point = versions_endpoint.end() + function_match.end()
    
    # Define the new endpoint
    new_endpoint = """

@api_bp.route('/version-info/<version_id>')
def get_version_info(version_id):
    \"\"\"Get information about a specific version without the full content\"\"\"
    version = OntologyVersion.query.get(version_id)
    
    if not version:
        return jsonify({'error': 'Version not found'}), 404
    
    # Return only metadata, not the full content
    return jsonify({
        'id': version.id,
        'ontology_id': version.ontology_id,
        'version_number': version.version_number,
        'commit_message': version.commit_message,
        'created_at': version.created_at.isoformat() if version.created_at else None
    })
"""
    
    # Insert the new endpoint
    new_content = content[:insertion_point] + new_endpoint + content[insertion_point:]
    
    # Add any missing imports
    if 'from app.models.ontology_version import OntologyVersion' not in new_content:
        import_line = 'from app.models.ontology_version import OntologyVersion'
        imports_end = new_content.find('\n\n', new_content.find('import'))
        if imports_end != -1:
            new_content = new_content[:imports_end] + '\n' + import_line + new_content[imports_end:]
    
    # Write the updated routes
    with open(routes_file, 'w') as f:
        f.write(new_content)
    
    print(f"Updated {routes_file} with version-info endpoint")
    return True

def main():
    """Main function to run the update"""
    print("Updating ontology editor with improved URL and version handling...")
    
    # Update the JavaScript
    if not update_editor_js():
        print("Failed to update editor.js")
        return 1
    
    # Update the HTML template
    if not update_editor_html():
        print("Failed to update editor.html template")
        return 1
    
    # Update the API routes
    if not update_api_routes():
        print("Failed to update API routes")
        return 1
    
    print("\nUpdate complete! The ontology editor now has:")
    print("✓ Improved URL parameter handling with History API")
    print("✓ Enhanced version management in the toolbar")
    print("✓ Better visual indicators for active ontologies and versions")
    print("✓ More consistent navigation between ontologies")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
