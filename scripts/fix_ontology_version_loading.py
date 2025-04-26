#!/usr/bin/env python3
"""
Script to fix the ontology version loading issue in the editor.js file.

The issue is that the editor.js file is trying to load versions using just 
the version ID, but the API expects both the ontology ID and version number.
"""
import os
import re
import sys

def fix_version_loading():
    """
    Fix the version loading in the editor.js file by updating:
    1. The loadVersion function to use the correct API endpoint format
    2. The version list items to include both version ID and version number
    3. The version click handler to pass version number instead of version ID
    """
    # Path to the editor.js file
    js_file_path = 'ontology_editor/static/js/editor.js'
    
    # Check if the file exists
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{js_file_path}.version_loading.bak'
    print(f"Creating backup of {js_file_path} to {backup_file_path}")
    
    with open(js_file_path, 'r') as f:
        original_content = f.read()
        
    with open(backup_file_path, 'w') as f:
        f.write(original_content)
    
    # Parse the content
    content = original_content
    
    # 1. Fix the updateVersionsList function to include version_number as a data attribute
    # Find the updateVersionsList function
    update_versions_pattern = re.compile(r'(function\s+updateVersionsList\s*\(versions\)\s*\{.*?)(return\s+`.*?version-id="\$\{version\.id\}".*?)(\n.*?\}\);)', re.DOTALL)
    
    # Update the function to add version_number as a data attribute
    if update_versions_pattern.search(content):
        content = update_versions_pattern.sub(
            r'\1return `\n            <li class="list-group-item" data-version-id="${version.id}" data-version-number="${version.version_number}">\3', 
            content
        )
        print("Updated updateVersionsList function to include version_number as a data attribute")
    else:
        print("Could not find updateVersionsList function. Is the file structure different?")
        return False
    
    # 2. Fix the version click handler to pass version number instead of version ID
    # Find the version click handler section
    version_click_pattern = re.compile(r'(document\.querySelectorAll\(\'#versionList li\'\)\.forEach\(item => \{.*?const\s+versionId\s*=\s*this\.dataset\.versionId;.*?)loadVersion\(versionId\);(.*?\}\);)', re.DOTALL)
    
    # Update the handler to use version_number
    if version_click_pattern.search(content):
        content = version_click_pattern.sub(
            r'\1const versionNumber = this.dataset.versionNumber;\n            loadVersion(versionNumber);\2', 
            content
        )
        print("Updated version click handler to pass version number instead of version ID")
    else:
        print("Could not find version click handler. Is the file structure different?")
        return False
    
    # 3. Fix the loadVersion function to use the correct API endpoint format
    # Find the loadVersion function
    load_version_pattern = re.compile(r'(function\s+loadVersion\s*\(\s*versionId\s*\)\s*\{.*?fetch\s*\(\s*)`/ontology-editor/api/versions/\$\{versionId\}`(.*?\})', re.DOTALL)
    
    # Update the function to use the correct endpoint format
    if load_version_pattern.search(content):
        # First update the function signature
        content = content.replace(
            "function loadVersion(versionId) {",
            "function loadVersion(versionNumber) {"
        )
        
        # Then update the fetch URL
        content = load_version_pattern.sub(
            r'\1`/ontology-editor/api/versions/${currentOntologyId}/${versionNumber}`\2', 
            content
        )
        print("Updated loadVersion function to use the correct API endpoint format")
    else:
        print("Could not find loadVersion function. Is the file structure different?")
        return False
    
    # Write the updated content back to the file
    with open(js_file_path, 'w') as f:
        f.write(content)
    
    print("Successfully updated editor.js file to fix the version loading issue")
    print("\nTo verify the fix:")
    print("1. Restart the server if necessary")
    print("2. Open the ontology editor and check if clicking on version numbers works")
    print("3. Check the browser console for any errors")
    
    return True

if __name__ == "__main__":
    if fix_version_loading():
        print("\nFix applied successfully!")
    else:
        print("\nFailed to apply fix. Please check the error messages above.")
