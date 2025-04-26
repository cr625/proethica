#!/usr/bin/env python3
"""
Script to fix escaped quotes in diff.js which are causing JavaScript syntax errors.
"""
import os
import re

def fix_diff_js_quotes():
    """
    Fix the escaped quotes in diff.js that are causing syntax errors.
    """
    # Path to the diff.js file
    js_file_path = 'ontology_editor/static/js/diff.js'
    
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{js_file_path}.quotes.bak'
    print(f"Creating backup of {js_file_path} to {backup_file_path}")
    
    with open(js_file_path, 'r') as f:
        content = f.read()
    
    with open(backup_file_path, 'w') as f:
        f.write(content)
    
    # Fix escaped single quotes
    # In JavaScript, we don't need to escape single quotes when using template literals (backticks)
    # or when inside double quotes, and vice versa
    
    # Check if there are escaped quotes in string literals
    escaped_quotes_pattern = r'\'diffFrom\w+\''
    if re.search(escaped_quotes_pattern, content):
        # Replace escaped quotes in template literals
        modified_content = content.replace("\'diffFromInfo\'", "'diffFromInfo'")
        modified_content = modified_content.replace("\'diffToInfo\'", "'diffToInfo'")
        modified_content = modified_content.replace("\'diffFromCommitSection\'", "'diffFromCommitSection'")
        modified_content = modified_content.replace("\'diffToCommitSection\'", "'diffToCommitSection'")
        modified_content = modified_content.replace("\'none\'", "'none'")
        
        # Write the modified content back
        with open(js_file_path, 'w') as f:
            f.write(modified_content)
        
        print("Fixed escaped quotes in JavaScript template literals")
        return True
    else:
        print("No escaped quotes found that need fixing")
        return False

if __name__ == "__main__":
    if fix_diff_js_quotes():
        print("\nJavaScript quote escaping fix applied successfully!")
    else:
        print("\nFailed to apply JavaScript quote escaping fix. Please check the error messages above.")
