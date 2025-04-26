#!/usr/bin/env python3
"""
Script to fix the ontology version loading issue in the editor.js file.
This is an improved version that handles all versionId references.

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
    4. All references to versionId within the loadVersion function
    """
    # Path to the editor.js file
    js_file_path = 'ontology_editor/static/js/editor.js'
    
    # Check if the file exists
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{js_file_path}.version_loading_v2.bak'
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
    
    # 3. Fix the loadVersion function signature and implementation
    # First update the function signature and JSDoc comment
    function_sig_pattern = re.compile(r'(/\*\*\n \* Load a specific version into the editor\n \*\n \* @param \{string\} versionId.*?\*/\n)(function\s+loadVersion\s*\(\s*versionId\s*\)\s*\{)', re.DOTALL)
    
    if function_sig_pattern.search(content):
        content = function_sig_pattern.sub(
            r'/**\n * Load a specific version into the editor\n *\n * @param {string} versionNumber - Number of the version to load\n */\n\1versionNumber)', 
            content
        )
        print("Updated loadVersion function signature and JSDoc comment")
    else:
        print("Could not find loadVersion function signature. Is the file structure different?")
        return False
    
    # 4. Fix the fetch URL in the loadVersion function
    fetch_url_pattern = re.compile(r'(function\s+loadVersion\s*\(\s*[^)]+\)\s*\{.*?fetch\s*\(\s*)`\/ontology-editor\/api\/versions\/\$\{[^}]+\}`(.*?\})', re.DOTALL)
    
    if fetch_url_pattern.search(content):
        content = fetch_url_pattern.sub(
            r'\1`/ontology-editor/api/versions/${currentOntologyId}/${versionNumber}`\2', 
            content
        )
        print("Updated fetch URL in loadVersion function")
    else:
        print("Could not find fetch URL pattern in loadVersion function. Is the file structure different?")
        return False
    
    # 5. Fix the version item selector in the loadVersion function
    version_item_pattern = re.compile(r'(const\s+versionItem\s*=\s*document\.querySelector\s*\(\s*)`#versionList\s+li\[data-version-id="\$\{versionId\}"\]`(.*?\));', re.DOTALL)
    
    if version_item_pattern.search(content):
        content = version_item_pattern.sub(
            r'\1`#versionList li[data-version-number="${versionNumber}"]`\2', 
            content
        )
        print("Updated version item selector in loadVersion function")
    else:
        print("Could not find version item selector pattern. Is the file structure different?")
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
