#!/usr/bin/env python
"""
Comprehensive script to fix multiple ontology editor issues.
This script fixes:
1. Version loading: The UI is trying to load version 12 which doesn't exist
2. ACE editor options: misspelled option names in editor.js
"""
import sys
import os
import re

def fix_editor_issues():
    """
    Fix multiple issues with the ontology editor.
    """
    print("Fixing ontology editor issues...")
    
    # 1. Fix the ACE editor options
    js_file_path = 'ontology_editor/static/js/editor.js'
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create a backup if it doesn't already exist
    js_backup_file_path = 'ontology_editor/static/js/editor.js.comprehensive.bak'
    if not os.path.exists(js_backup_file_path):
        print(f"Creating backup of {js_file_path} to {js_backup_file_path}")
        with open(js_file_path, 'r') as f:
            original_content = f.read()
        
        with open(js_backup_file_path, 'w') as f:
            f.write(original_content)
    
    # Read current JavaScript content
    with open(js_file_path, 'r') as f:
        js_content = f.read()
    
    print("Fixing ACE editor options...")
    
    # Fix the misspelled options - ensure exact replacement
    js_content = re.sub(
        r'enableBasicAutoComplete:\s*true',
        'enableBasicAutocompletion: true',
        js_content
    )
    
    js_content = re.sub(
        r'enableLiveAutoComplete:\s*true',
        'enableLiveAutocompletion: true', 
        js_content
    )
    
    # 2. Fix the version loading in JavaScript (use version_number parameter in data-version-id)
    print("Fixing version loading in editor.js...")
    
    # Find the part where it creates version list items
    version_list_pattern = r'const items = versions\.map\(version => \{.*?\}\)\.join\(\'\'\);'
    version_list_match = re.search(version_list_pattern, js_content, re.DOTALL)
    
    if version_list_match:
        print("Found version list generation code")
        original_code = version_list_match.group(0)
        
        # Replace data-version-id with version_number instead of id
        modified_code = original_code.replace(
            'data-version-id="${version.id}"',
            'data-version-number="${version.version_number}"'
        )
        
        js_content = js_content.replace(original_code, modified_code)
        print("Updated version list to use version_number instead of id")
    else:
        print("Warning: Could not find version list generation code")
        
    # Update the loadVersion function to use version_number instead of version ID
    load_version_pattern = r'function loadVersion\(versionId\) \{[\s\S]*?\}'
    load_version_match = re.search(load_version_pattern, js_content)
    
    if load_version_match:
        print("Found loadVersion function")
        
        # Replace with updated function that uses version_number
        updated_load_version = """function loadVersion(versionNumber) {
    // Show loading indicator
    const editorContainer = document.getElementById('editorContainer');
    const loadingOverlay = document.createElement('div');
    loadingOverlay.className = 'loading-overlay';
    loadingOverlay.innerHTML = `
        <div class="spinner-border" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
    `;
    editorContainer.appendChild(loadingOverlay);
    
    // Fetch the version content
    fetch(`/ontology-editor/api/versions/${currentOntologyId}/${versionNumber}`)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load version');
            }
            return response.json();
        })
        .then(data => {
            // Update editor content
            editor.setValue(data.content);
            editor.clearSelection();
            
            // Reset dirty flag (loading a version doesn't make the editor dirty)
            isEditorDirty = false;
            document.getElementById('saveBtn').disabled = true;
            
            // Highlight the selected version in the list
            document.querySelectorAll('#versionList li').forEach(item => {
                item.classList.remove('active');
            });
            
            const versionItem = document.querySelector(`#versionList li[data-version-number="${versionNumber}"]`);
            if (versionItem) {
                versionItem.classList.add('active');
            }
            
            // Remove loading indicator
            editorContainer.removeChild(loadingOverlay);
        })
        .catch(error => {
            console.error('Error loading version:', error);
            
            // Display error
            editorContainer.removeChild(loadingOverlay);
            alert(`Error loading version: ${error.message}`);
        });
}"""
        
        js_content = js_content.replace(load_version_match.group(0), updated_load_version)
        print("Updated loadVersion function to use version_number")
    else:
        print("Warning: Could not find loadVersion function")
    
    # Update the click event handler for versions
    click_handler_pattern = r'const versionId = this\.dataset\.versionId;\s*loadVersion\(versionId\);'
    updated_click_handler = 'const versionNumber = this.dataset.versionNumber;\n            loadVersion(versionNumber);'
    
    js_content = js_content.replace(click_handler_pattern, updated_click_handler)
    print("Updated version click handler to use version_number")
    
    # Write the updated content back to the file
    with open(js_file_path, 'w') as f:
        f.write(js_content)
     
    print("All editor fixes applied!")
    return True

if __name__ == "__main__":
    if fix_editor_issues():
        print("Successfully fixed ontology editor issues")
    else:
        print("Failed to fix some ontology editor issues")
