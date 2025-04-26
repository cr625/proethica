#!/usr/bin/env python3
"""
Script to add click handler for the close-diff footer button.
"""
import os
import re
import sys

def add_footer_close_handler():
    """
    Add click handler for the close button in the diff modal footer.
    """
    # Path to the diff.js file
    js_file_path = 'ontology_editor/static/js/diff.js'
    
    # Check if the file exists
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{js_file_path}.footer_handler.bak'
    print(f"Creating backup of {js_file_path} to {backup_file_path}")
    
    with open(js_file_path, 'r') as f:
        content = f.read()
        
    with open(backup_file_path, 'w') as f:
        f.write(content)
    
    # Find the setupDiffModal function
    setup_modal_pattern = re.compile(r'function\s+setupDiffModal\s*\(\s*\)\s*\{(.*?)(\}\s*)$', re.DOTALL | re.MULTILINE)
    
    match = setup_modal_pattern.search(content)
    if not match:
        print("Could not find setupDiffModal function")
        return False
    
    # Get the function body
    function_body = match.group(1)
    
    # Check if the handler is already added
    if "closeDiffBtnFooter" in function_body:
        print("Footer close handler already exists, no changes needed")
        return True
    
    # Add the handler
    modified_function_body = function_body + """
    // Footer close button event
    document.getElementById('closeDiffBtnFooter').addEventListener('click', function() {
        document.getElementById('diffModal').classList.remove('show');
        document.getElementById('diffModalBackdrop').style.display = 'none';
    });
"""
    
    # Update the function
    modified_content = content.replace(function_body, modified_function_body)
    
    # Write the updated content back
    with open(js_file_path, 'w') as f:
        f.write(modified_content)
    
    print("Successfully added footer close button handler")
    return True

if __name__ == "__main__":
    if add_footer_close_handler():
        print("\nFooter close handler added successfully!")
    else:
        print("\nFailed to add footer close handler. Please check the error messages above.")
