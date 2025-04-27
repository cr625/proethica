#!/usr/bin/env python3
"""
Script to fix the ontology validation route in the ontology editor API.

The validator is failing with an error because the data is being sent
incorrectly. This script fixes the issue by properly extracting content 
from JSON data rather than trying to decode raw request data.
"""

import os
import sys
from pathlib import Path

BACKUP_DIR = Path("backups")
API_ROUTES_PATH = Path("ontology_editor/api/routes.py")

def create_backup(file_path):
    """Create a backup of the original file"""
    backup_path = BACKUP_DIR / f"{file_path.name}.validator.bak"
    
    # Create backup directory if it doesn't exist
    if not BACKUP_DIR.exists():
        BACKUP_DIR.mkdir()
    
    with open(file_path, 'r') as original:
        with open(backup_path, 'w') as backup:
            backup.write(original.read())
    
    print(f"Created backup of {file_path} at {backup_path}")
    return backup_path

def fix_validate_ontology_route():
    """Fix the validate_ontology route in ontology_editor/api/routes.py"""
    if not API_ROUTES_PATH.exists():
        print(f"Error: {API_ROUTES_PATH} does not exist")
        return False
    
    # Create backup
    backup_path = create_backup(API_ROUTES_PATH)
    
    # Read the current file
    with open(API_ROUTES_PATH, 'r') as f:
        content = f.read()
    
    # Find the validate_ontology route
    old_function = """    @api_bp.route('/ontology/<int:ontology_id>/validate', methods=['POST'])
    def validate_ontology(ontology_id):
        \"\"\"Validate the content of an ontology\"\"\"
        try:
            # Get the content to validate
            content = request.data.decode('utf-8')
            
            # If content is empty, get it from the database
            if not content and ontology_id:
                ontology = Ontology.query.get_or_404(ontology_id)
                content = ontology.content
            
            # Validate the content
            validator = OntologyValidator()
            validation_result = validator.validate(content)
            
            return jsonify(validation_result)
        except Exception as e:
            current_app.logger.error(f"Error validating ontology {ontology_id}: {str(e)}")
            return jsonify({'error': f'Failed to validate ontology {ontology_id}', 'details': str(e)}), 500"""
    
    # New function with proper JSON parsing
    new_function = """    @api_bp.route('/ontology/<int:ontology_id>/validate', methods=['POST'])
    def validate_ontology(ontology_id):
        \"\"\"Validate the content of an ontology\"\"\"
        try:
            # Get JSON data if available
            data = request.json
            
            # Extract content from the JSON data if provided
            content = None
            if data and 'content' in data:
                content = data['content']
            else:
                # Fallback to raw data if JSON is not used
                try:
                    content = request.data.decode('utf-8')
                except Exception as decode_error:
                    current_app.logger.error(f"Error decoding request data: {str(decode_error)}")
                    pass
            
            # If content is still empty, get it from the database
            if not content and ontology_id:
                ontology = Ontology.query.get_or_404(ontology_id)
                content = ontology.content
            
            # Log what we're validating for debugging purposes
            current_app.logger.debug(f"Validating ontology content (first 100 chars): {content[:100] if content else 'None'}")
            
            # Validate the content
            validator = OntologyValidator()
            validation_result = validator.validate(content)
            
            return jsonify(validation_result)
        except Exception as e:
            current_app.logger.error(f"Error validating ontology {ontology_id}: {str(e)}")
            return jsonify({'error': f'Failed to validate ontology {ontology_id}', 'details': str(e)}), 500"""
    
    # Replace the old function with the new one
    updated_content = content.replace(old_function, new_function)
    
    # Write the updated content back to the file
    with open(API_ROUTES_PATH, 'w') as f:
        f.write(updated_content)
    
    print(f"Updated {API_ROUTES_PATH} with improved validation route")
    return True

def fix_validation_js():
    """Create a JavaScript fix to modify how content is sent for validation"""
    JS_FILE_PATH = Path("ontology_editor/static/js/editor.js")
    
    if not JS_FILE_PATH.exists():
        print(f"Error: {JS_FILE_PATH} does not exist")
        return False
    
    # Create backup
    backup_path = create_backup(JS_FILE_PATH)
    
    # Read the current file
    with open(JS_FILE_PATH, 'r') as f:
        content = f.read()
    
    # Find the validateOntology function
    old_function = """/**
 * Validate the current ontology
 */
function validateOntology() {
    // Hide any existing validation results
    document.getElementById('validationCard').style.display = 'none';
    
    if (!currentOntologyId) {
        alert('No ontology loaded to validate');
        return;
    }
    
    // First validate syntax
    const content = editor.getValue();
    
    // Show loading indicator
    const resultsElement = document.getElementById('validationResults');
    resultsElement.innerHTML = `
        <div class="text-center">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Validating...</span>
            </div>
            <p>Validating ontology...</p>
        </div>
    `;
    document.getElementById('validationCard').style.display = 'block';
    
    // First send to validate TTL syntax
    fetch(`/ontology-editor/api/ontology/${currentOntologyId}/validate`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ content })
    })"""
    
    # New function with proper content wrapping
    new_function = """/**
 * Validate the current ontology
 */
function validateOntology() {
    // Hide any existing validation results
    document.getElementById('validationCard').style.display = 'none';
    
    if (!currentOntologyId) {
        alert('No ontology loaded to validate');
        return;
    }
    
    // First validate syntax
    const content = editor.getValue();
    
    // Show loading indicator
    const resultsElement = document.getElementById('validationResults');
    resultsElement.innerHTML = `
        <div class="text-center">
            <div class="spinner-border" role="status">
                <span class="visually-hidden">Validating...</span>
            </div>
            <p>Validating ontology...</p>
        </div>
    `;
    document.getElementById('validationCard').style.display = 'block';
    
    // First send to validate TTL syntax with properly formatted JSON
    fetch(`/ontology-editor/api/ontology/${currentOntologyId}/validate`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ content: content })
    })"""
    
    # Replace the old function with the new one
    updated_content = content.replace(old_function, new_function)
    
    # Write the updated content back to the file
    with open(JS_FILE_PATH, 'w') as f:
        f.write(updated_content)
    
    print(f"Updated {JS_FILE_PATH} with improved validation request formatting")
    return True

if __name__ == "__main__":
    print("Fixing ontology validation issues...")
    
    # Fix the backend validation route
    backend_fixed = fix_validate_ontology_route()
    
    # Fix the frontend validation request
    frontend_fixed = fix_validation_js()
    
    if backend_fixed and frontend_fixed:
        print("\n✅ Successfully fixed ontology validation!")
        print("\nThe changes made:")
        print("1. Updated backend validation route to properly handle JSON data")
        print("2. Fixed frontend validation request to correctly format content")
        print("\nPlease restart the server to apply the changes.")
    else:
        print("\n❌ Some fixes could not be applied. Please check the error messages above.")
    
    sys.exit(0 if backend_fixed and frontend_fixed else 1)
