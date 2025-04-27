#!/usr/bin/env python3
"""
Script to fix the data undefined error in diff.js.
"""
import os
import re

def fix_diff_data_undefined():
    """
    Fix the 'Cannot read properties of undefined (reading 'number')' error
    by adding proper checks before accessing data properties.
    """
    # Path to the diff.js file
    js_file_path = 'ontology_editor/static/js/diff.js'
    
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{js_file_path}.data_undefined.bak'
    print(f"Creating backup of {js_file_path} to {backup_file_path}")
    
    with open(js_file_path, 'r') as f:
        content = f.read()
    
    with open(backup_file_path, 'w') as f:
        f.write(content)
    
    # Add safe property access in the data handling section
    # Look for sections where data.from_version.number is accessed
    updated_content = content
    
    # 1. First fix the setting of diffFromInfo and diffToInfo
    diffFromInfo_pattern = r'document\.getElementById\(\'diffFromInfo\'\)\.innerText\s*=\s*`Version \$\{data\.from_version\.number\}.*?\`;'
    if re.search(diffFromInfo_pattern, updated_content):
        updated_content = re.sub(
            diffFromInfo_pattern,
            """document.getElementById('diffFromInfo').innerText = 
                data && data.from_version ? 
                `Version ${data.from_version.number || 'N/A'} - ${formatDate(data.from_version.created_at || null)}` : 
                'Version information unavailable';""",
            updated_content
        )
        print("Added safe access for diffFromInfo")
    
    diffToInfo_pattern = r'document\.getElementById\(\'diffToInfo\'\)\.innerText\s*=\s*`Version \$\{data\.to_version\.number\}.*?\`;'
    if re.search(diffToInfo_pattern, updated_content):
        updated_content = re.sub(
            diffToInfo_pattern,
            """document.getElementById('diffToInfo').innerText = 
                data && data.to_version ? 
                `Version ${data.to_version.number || 'N/A'} - ${formatDate(data.to_version.created_at || null)}` : 
                'Version information unavailable';""",
            updated_content
        )
        print("Added safe access for diffToInfo")
    
    # 2. Fix the commit message handling
    commit_message_pattern = r'if\s*\(data\.from_version\.commit_message\)'
    if re.search(commit_message_pattern, updated_content):
        updated_content = re.sub(
            commit_message_pattern,
            "if (data && data.from_version && data.from_version.commit_message)",
            updated_content
        )
        print("Added safe access check for from_version commit_message")
    
    to_commit_message_pattern = r'if\s*\(data\.to_version\.commit_message\)'
    if re.search(to_commit_message_pattern, updated_content):
        updated_content = re.sub(
            to_commit_message_pattern,
            "if (data && data.to_version && data.to_version.commit_message)",
            updated_content
        )
        print("Added safe access check for to_version commit_message")
    
    # 3. Add a general data validation check before processing
    # Find the line where we start processing data
    data_processing_start = "// Display the diff"
    data_processing_idx = updated_content.find(data_processing_start)
    
    if data_processing_idx != -1:
        # Insert validation check before this line
        validation_check = """
            // Validate data structure
            if (!data || !data.diff) {
                diffContent.innerHTML = `
                    <div class="alert alert-danger">
                        <h5>Invalid Response Format</h5>
                        <p>The server response did not contain the expected data format.</p>
                        <pre>${JSON.stringify(data, null, 2)}</pre>
                    </div>
                `;
                return;
            }
            
        """
        
        updated_content = (
            updated_content[:data_processing_idx] + 
            validation_check + 
            updated_content[data_processing_idx:]
        )
        print("Added data validation check")
    
    # Write the modified content back
    with open(js_file_path, 'w') as f:
        f.write(updated_content)
    
    print("Added proper checks before accessing data properties")
    return True

if __name__ == "__main__":
    if fix_diff_data_undefined():
        print("\nData undefined fix applied successfully!")
    else:
        print("\nFailed to apply data undefined fix. Please check the error messages above.")
