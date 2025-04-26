#!/usr/bin/env python3
"""
Script to update the front-end diff viewer to fix JavaScript error handling.
"""
import os
import re
import sys

def fix_frontend_diff_handler():
    """
    Fix the JavaScript error handling in the diff.js file.
    """
    # Path to the diff.js file
    js_file_path = 'ontology_editor/static/js/diff.js'
    
    # Check if the file exists
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{js_file_path}.error_handling.bak'
    print(f"Creating backup of {js_file_path} to {backup_file_path}")
    
    with open(js_file_path, 'r') as f:
        original_content = f.read()
        
    with open(backup_file_path, 'w') as f:
        f.write(original_content)
    
    # Fix the loadDiff function to handle the case where same version is compared
    load_diff_pattern = re.compile(r'(function\s+loadDiff\s*\(\s*fromVersion\s*,\s*toVersion\s*\)\s*\{.*?fetch\s*\(url\))(.*?)(\.catch\s*\(error\s*=>.*?)(\}\);)', re.DOTALL)
    
    if load_diff_pattern.search(original_content):
        # Fix error handling in the fetch callback
        updated_content = load_diff_pattern.sub(
            # Group 1: function declaration and fetch call
            r'\1'
            # Add improved error handling and checking the response status
            r'.then(response => {'
            r'            if (!response.ok) {'
            r'                throw new Error(`HTTP error ${response.status}: ${response.statusText}` || "Failed to load diff");'
            r'            }'
            r'            return response.json();'
            r'        })'
            # Group 2: process successful response
            r'\2'
            # Group 3: catch error, with better display
            r'\3'
            # Group 4: closing brackets
            r'\4',
            original_content
        )
        
        print("Fixed error handling in loadDiff function")
    else:
        print("Could not find loadDiff function pattern. The file structure may have changed.")
        return False
    
    # Fix handling for same version comparison
    updated_content = re.sub(
        r'(const\s+url\s*=\s*`/ontology-editor/api/versions/\$\{currentOntologyId\}/diff\?from=\$\{fromVersion\}&to=\$\{toVersion\}&format=\$\{format\}`;)',
        r'// Check if comparing the same version\n'
        r'    if (fromVersion === toVersion) {\n'
        r'        // Display a message about same version comparison\n'
        r'        diffContent.innerHTML = `\n'
        r'            <div class="alert alert-info">\n'
        r'                <h5>Same Version Selected</h5>\n'
        r'                <p>You have selected the same version for comparison. There are no differences to display.</p>\n'
        r'            </div>\n'
        r'        `;\n'
        r'        \n'
        r'        // Update metadata\n'
        r'        document.getElementById(\'diffFromInfo\').innerText = \n'
        r'            `Version ${fromVersion}`;\n'
        r'            \n'
        r'        document.getElementById(\'diffToInfo\').innerText = \n'
        r'            `Version ${toVersion} (Same)`;\n'
        r'            \n'
        r'        // Hide commit message sections\n'
        r'        document.getElementById(\'diffFromCommitSection\').style.display = \'none\';\n'
        r'        document.getElementById(\'diffToCommitSection\').style.display = \'none\';\n'
        r'        \n'
        r'        return; // Exit early\n'
        r'    }\n'
        r'    \n'
        r'    \1',
        updated_content
    )
    print("Added handling for same version comparison")
    
    # Improve error message display
    updated_content = re.sub(
        r'(diffContent\.innerHTML\s*=\s*`\s*<div class="alert alert-danger">\s*Error loading diff: \$\{error\.message\}\s*</div>\s*`;)',
        r'diffContent.innerHTML = `\n'
        r'                <div class="alert alert-danger">\n'
        r'                    <h5>Error Loading Diff</h5>\n'
        r'                    <p>${error.message}</p>\n'
        r'                    ${error.stack ? `<details><summary>Technical Details</summary><pre>${error.stack}</pre></details>` : ""}\n'
        r'                </div>\n'
        r'                <div class="mt-3">\n'
        r'                    <p><strong>Troubleshooting Suggestions:</strong></p>\n'
        r'                    <ul>\n'
        r'                        <li>Check that the server is running</li>\n'
        r'                        <li>Make sure both versions exist in the database</li>\n'
        r'                        <li>Try refreshing the page and trying again</li>\n'
        r'                    </ul>\n'
        r'                </div>\n'
        r'            `;',
        updated_content
    )
    print("Improved error message display")
    
    # Fix closeDiffBtnFooter click handler
    if 'document.getElementById(\'closeDiffBtnFooter\')' in updated_content:
        updated_content = updated_content.replace(
            'function setupDiffModal() {',
            'function setupDiffModal() {\n'
            '    // Close button in footer event\n'
            '    document.getElementById(\'closeDiffBtnFooter\').addEventListener(\'click\', function() {\n'
            '        document.getElementById(\'diffModal\').classList.remove(\'show\');\n'
            '        document.getElementById(\'diffModalBackdrop\').style.display = \'none\';\n'
            '    });\n'
        )
        print("Added click handler for footer close button")
    else:
        print("Footer close button not found, skipping handler addition")
    
    # Write the updated content back
    with open(js_file_path, 'w') as f:
        f.write(updated_content)
    
    print(f"Successfully updated {js_file_path} with improved error handling")
    print("\nKey fixes:")
    print("1. Added check for comparing same version")
    print("2. Improved error handling in fetch() calls")
    print("3. Added more detailed error messages")
    print("4. Added close button handler for footer button")
    
    return True

if __name__ == "__main__":
    if fix_frontend_diff_handler():
        print("\nDiff viewer frontend fix applied successfully!")
    else:
        print("\nFailed to apply fix. Please check the error messages above.")
