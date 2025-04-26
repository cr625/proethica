#!/usr/bin/env python3
"""
Script to fix the compare button functionality in diff.js.
"""
import os
import re

def fix_add_compare_buttons():
    """
    Fix the compare button functionality in diff.js that is missing from the interface.
    """
    # Path to the diff.js file
    js_file_path = 'ontology_editor/static/js/diff.js'
    
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{js_file_path}.compare.bak'
    print(f"Creating backup of {js_file_path} to {backup_file_path}")
    
    with open(js_file_path, 'r') as f:
        content = f.read()
    
    with open(backup_file_path, 'w') as f:
        f.write(content)
    
    # Check if addCompareButtonsToVersions function is properly called when document is loaded
    doc_ready_pattern = r'document\.addEventListener\([\'"]DOMContentLoaded[\'"],[^)]*\)'
    if not re.search(doc_ready_pattern, content):
        # Add document ready event listener to call addCompareButtonsToVersions
        # Find the end of file or specific marker to add the event listener
        doc_ready_code = """

// Make sure to add compare buttons when the document is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Add compare buttons to version items
    addCompareButtonsToVersions();
    
    // Setup the diff modal
    setupDiffModal();
});
"""
        
        # Add the document ready code before the end of the file
        modified_content = content + doc_ready_code
        
        # Write the modified content back
        with open(js_file_path, 'w') as f:
            f.write(modified_content)
        
        print("Added document ready event listener to initialize compare buttons")
        return True
    
    # Check the implementation of addCompareButtonsToVersions function
    add_buttons_pattern = r'function\s+addCompareButtonsToVersions\s*\(\s*\)\s*\{[^}]*\}'
    match = re.search(add_buttons_pattern, content)
    
    if match:
        # Find specific issues in the implementation
        button_creation_pattern = r'btn\.textContent\s*=\s*[\'"]Compare[\'"]'
        if not re.search(button_creation_pattern, content):
            # Fix the button creation code if it's missing the text
            old_function = match.group(0)
            
            # Create an improved implementation
            new_function = """
/**
 * Add compare buttons to each version item in the list
 */
function addCompareButtonsToVersions() {
    // Get all version items
    const versionItems = document.querySelectorAll('#versionList li');

    // Remove any existing compare buttons first
    document.querySelectorAll('.compare-version-btn').forEach(btn => {
        btn.remove();
    });

    // Add new compare buttons to each item
    versionItems.forEach((item) => {
        const versionNumber = item.dataset.versionNumber;
        if (!versionNumber) return;
        
        // Create the compare button
        const btn = document.createElement('button');
        btn.className = 'btn btn-sm btn-outline-primary compare-version-btn ms-2';
        btn.textContent = 'Compare';
        btn.title = 'Compare with another version';
        
        // Add click event handler
        btn.addEventListener('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            showDiffModal(versionNumber);
        });

        // Find where to insert the button (after version info)
        const versionInfo = item.querySelector('.version-info');
        if (versionInfo) {
            versionInfo.appendChild(btn);
        } else {
            // Fallback to append to the item itself
            item.appendChild(btn);
        }
    });

    console.log(`Added compare buttons to ${versionItems.length} version items`);
}
"""
            # Replace the old function with the new implementation
            modified_content = content.replace(old_function, new_function)
            
            # Write the modified content back
            with open(js_file_path, 'w') as f:
                f.write(modified_content)
            
            print("Fixed addCompareButtonsToVersions function implementation")
            return True
        else:
            print("addCompareButtonsToVersions function seems to be implemented correctly")
    
    # If we made it here, no changes were needed
    print("No issues found with compare button functionality")
    return True

if __name__ == "__main__":
    if fix_add_compare_buttons():
        print("\nCompare button functionality fix applied successfully!")
    else:
        print("\nFailed to apply compare button functionality fix. Please check the error messages above.")
