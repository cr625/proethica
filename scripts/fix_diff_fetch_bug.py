#!/usr/bin/env python3
"""
Script to fix the fetch double response.json() bug in diff.js.
"""
import os
import re

def fix_diff_fetch_bug():
    """
    Fix the bug where response.json() is called twice in the fetch chain.
    """
    # Path to the diff.js file
    js_file_path = 'ontology_editor/static/js/diff.js'
    
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{js_file_path}.fetch.bak'
    print(f"Creating backup of {js_file_path} to {backup_file_path}")
    
    with open(js_file_path, 'r') as f:
        content = f.read()
    
    with open(backup_file_path, 'w') as f:
        f.write(content)
    
    # Fix the fetch chain with double response.json() call
    fetch_pattern = r'fetch\(url\)\.then\(.*?\).*?\.then\(response => \{[^}]*return response\.json\(\);[^}]*\}\)'
    if re.search(fetch_pattern, content):
        # Fix fetch chain to avoid calling response.json() twice
        modified_content = re.sub(
            fetch_pattern,
            """fetch(url).then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}: ${response.statusText}` || "Failed to load diff");
            }
            return response.json();
        })""",
            content
        )
        
        # Write the modified content back
        with open(js_file_path, 'w') as f:
            f.write(modified_content)
        
        print("Fixed fetch chain to avoid calling response.json() twice")
        return True
    
    # An alternative approach in case regex doesn't match
    if "fetch(url).then" in content and "return response.json();" in content and content.count("return response.json();") > 1:
        # The problem is that response.json() is being called twice
        # Find the fetch callback chain and fix it manually
        
        # Locate the problematic fetch chain
        start_index = content.find("fetch(url)")
        if start_index == -1:
            print("Could not find fetch(url) in the content")
            return False
            
        # Find the end of the first then block
        first_then_end = content.find(".then", start_index + 10)
        if first_then_end == -1:
            print("Could not find end of first then block")
            return False
            
        # Find the next then block
        second_then_start = content.find(".then", first_then_end + 5)
        if second_then_start == -1:
            print("Could not find second then block")
            return False
            
        # If second then block checks response.ok again, it's redundant
        response_ok_check = content.find("response.ok", second_then_start, second_then_start + 150)
        if response_ok_check != -1:
            # This is the problematic pattern - remove the redundant then block
            first_part = content[:first_then_end]
            
            # Find the end of the second then block
            second_then_end = content.find(".then", second_then_start + 5)
            if second_then_end == -1:
                # If there's no third then, find the closing bracket
                brackets = 1
                pos = second_then_start + 5
                while brackets > 0 and pos < len(content):
                    if content[pos] == '(':
                        brackets += 1
                    elif content[pos] == ')':
                        brackets -= 1
                    pos += 1
                    
                second_then_end = pos
            
            # Skip the second then block entirely
            third_part = content[second_then_end:]
            
            # Put it back together
            modified_content = first_part + third_part
            
            # Write the modified content back
            with open(js_file_path, 'w') as f:
                f.write(modified_content)
            
            print("Removed redundant response.ok check and duplicate response.json() call")
            return True
            
    # If we've made it here, try a direct string replacement approach
    problematic_code = """fetch(url).then(response => {            if (!response.ok) {                throw new Error(`HTTP error ${response.status}: ${response.statusText}` || "Failed to load diff");            }            return response.json();        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to load diff');
            }
            return response.json();
        })"""
    
    fixed_code = """fetch(url).then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error ${response.status}: ${response.statusText}` || "Failed to load diff");
            }
            return response.json();
        })"""
    
    if problematic_code in content:
        modified_content = content.replace(problematic_code, fixed_code)
        
        # Write the modified content back
        with open(js_file_path, 'w') as f:
            f.write(modified_content)
        
        print("Fixed fetch chain using direct string replacement")
        return True
    
    print("No fetch chain issue found or pattern not recognized")
    return False

if __name__ == "__main__":
    if fix_diff_fetch_bug():
        print("\nFetch chain fix applied successfully!")
    else:
        print("\nFailed to apply fetch chain fix. Please check the error messages above.")
