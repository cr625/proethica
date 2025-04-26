#!/usr/bin/env python
"""
Fix a syntax error in the editor.js file that's preventing the ontology editor from working.
The issue appears to be a corrupted loadVersion function that has duplicate code.
"""
import os

def fix_syntax_error():
    """
    Fix the syntax error in the editor.js file.
    """
    js_file_path = 'ontology_editor/static/js/editor.js'
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = 'ontology_editor/static/js/editor.js.syntax_fix.bak'
    print(f"Creating backup of {js_file_path} to {backup_file_path}")
    with open(js_file_path, 'r') as f:
        original_content = f.read()
    
    with open(backup_file_path, 'w') as f:
        f.write(original_content)
    
    # The issue appears to be that there are two loadVersion functions
    # or a corrupted one. Let's create a correct version of the file
    # by replacing the entire loadVersion function with the correct one.
    correct_load_version_function = """
/**
 * Load a specific version into the editor
 * 
 * @param {string} versionNumber - Number of the version to load
 */
function loadVersion(versionNumber) {
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
}
"""
    
    # Fix the click handler for version list items
    correct_click_handler = """
    // Add click event listeners
    document.querySelectorAll('#versionList li').forEach(item => {
        item.addEventListener('click', function() {
            // Check if there are unsaved changes
            if (isEditorDirty && !confirm('You have unsaved changes. Do you want to discard them?')) {
                return;
            }
            
            const versionNumber = this.dataset.versionNumber;
            loadVersion(versionNumber);
        });
    });
"""
    
    # Read the file
    with open(js_file_path, 'r') as f:
        content = f.read()
    
    # Find where the loadVersion function starts and ends
    # This is a bit tricky due to the corruption, so we'll search for known parts
    start_marker = "/**\n * Load a specific version into the editor"
    end_marker_1 = "}\n\n/**\n * Validate the current ontology"
    end_marker_2 = "}\n\n  /**\n   * Validate the current ontology"
    
    # Try to find the bounds of the function
    start_index = content.find(start_marker)
    if start_index == -1:
        print("Could not find the start of the loadVersion function")
        return False
    
    # Try to find the end - first try one pattern, then the other
    end_index = content.find(end_marker_1, start_index)
    if end_index == -1:
        end_index = content.find(end_marker_2, start_index)
    
    if end_index == -1:
        print("Could not find the end of the loadVersion function")
        return False
    
    # Replace the function
    new_content = content[:start_index] + correct_load_version_function + content[end_index:]
    
    # Also fix the click handler
    click_handler_start = "    // Add click event listeners\n    document.querySelectorAll('#versionList li').forEach"
    click_handler_end = "    });"
    
    click_start_index = new_content.find(click_handler_start)
    if click_start_index != -1:
        # Find the end of this block - search for the next function after this
        click_end_index = new_content.find("});", click_start_index)
        if click_end_index != -1:
            click_end_index += 3  # Include the closing parenthesis and semicolon
            new_content = new_content[:click_start_index] + correct_click_handler + new_content[click_end_index:]
    
    # Write the new content
    with open(js_file_path, 'w') as f:
        f.write(new_content)
    
    print(f"Fixed syntax error in {js_file_path}")
    return True

if __name__ == "__main__":
    if fix_syntax_error():
        print("Successfully fixed editor.js syntax error")
    else:
        print("Failed to fix editor.js syntax error")
