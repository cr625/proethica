#!/usr/bin/env python3
"""
Script to fix the diff viewer version selection issue.
"""
import os
import re

def fix_diff_selections():
    """
    Fix the issue where diff viewer always compares version 11 to 11
    regardless of dropdown selections.
    """
    # Path to the diff.js file
    js_file_path = 'ontology_editor/static/js/diff.js'
    
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{js_file_path}.selections.bak'
    print(f"Creating backup of {js_file_path} to {backup_file_path}")
    
    with open(js_file_path, 'r') as f:
        content = f.read()
    
    with open(backup_file_path, 'w') as f:
        f.write(content)
    
    # Fix the showDiffModal function to ensure it's using the selected versions
    updated_content = content
    
    # 1. Fix version selection in showDiffModal function
    # Find the relevant code section at the end of showDiffModal function
    apply_btn_section = """
    // Apply button click
    document.getElementById('applyDiffBtn').addEventListener('click', function() {
        const selectedFromVersion = document.getElementById('diffFromVersion').value;
        const selectedToVersion = document.getElementById('diffToVersion').value;
        
        if (selectedFromVersion && selectedToVersion) {
            loadDiff(selectedFromVersion, selectedToVersion);
        }
    });
"""
    
    # Check if the modal is being shown and version selections set
    show_modal_pattern = r'document\.getElementById\(\'diffModal\'\)\.classList\.add\(\'show\'\);([\s\S]*?)// Apply button click'
    show_modal_match = re.search(show_modal_pattern, updated_content)
    
    if show_modal_match:
        # Add debug logging for versions
        debug_code = """
        // Debug version selections
        console.log('Modal opened with versions:', { fromVersion, selectedVersion: fromSelect.value, toVersion: toSelect.value });
"""
        updated_content = updated_content.replace(
            "document.getElementById('diffModal').classList.add('show');",
            "document.getElementById('diffModal').classList.add('show');" + debug_code
        )
        print("Added version selection debugging")
    
    # 2. Fix the loadDiff function to ensure URL parameters are correct
    url_pattern = r'const url = `\/ontology-editor\/api\/versions\/\$\{currentOntologyId\}\/diff\?from=\$\{fromVersion\}&to=\$\{toVersion\}&format=\$\{format\}`;'
    if re.search(url_pattern, updated_content):
        # Add debug logging before making the request
        url_debug = """
    // Debug URL parameters
    console.log('Loading diff with parameters:', { fromVersion, toVersion, format });
    const currentOntologyId = document.getElementById('currentOntologyId').value || document.body.dataset.ontologyId || '1';
"""
        updated_content = re.sub(
            url_pattern,
            url_debug + "    const url = `/ontology-editor/api/versions/${currentOntologyId}/diff?from=${fromVersion}&to=${toVersion}&format=${format}`;",
            updated_content
        )
        print("Added URL parameter debugging and improved ontology_id detection")
    
    # 3. Fix version selection dropdowns
    dropdown_selection_pattern = r'if \(fromVersion\) \{[\s\S]*?fromSelect\.value = fromVersion;[\s\S]*?\}'
    dropdown_selection_match = re.search(dropdown_selection_pattern, updated_content)
    
    if dropdown_selection_match:
        # Make sure fromVersion is explicitly set to the option value, and set toVersion to the next version
        fixed_dropdown_code = """
    // Set initial selections in dropdowns
    if (fromVersion) {
        // Set from version dropdown
        for (let i = 0; i < fromSelect.options.length; i++) {
            if (fromSelect.options[i].value === fromVersion) {
                fromSelect.selectedIndex = i;
                break;
            }
        }
        
        // Set to version to the next one (if available)
        const toSelect = document.getElementById('diffToVersion');
        if (versions.length > 1) {
            // Find current index
            const currentIndex = versions.findIndex(v => v.number === fromVersion);
            if (currentIndex >= 0) {
                // Set to version to the next highest version (or highest if this is the highest)
                const toIndex = Math.max(0, currentIndex - 1);
                const toVersion = versions[toIndex].number;
                
                for (let i = 0; i < toSelect.options.length; i++) {
                    if (toSelect.options[i].value === toVersion) {
                        toSelect.selectedIndex = i;
                        break;
                    }
                }
            }
        }
    }
"""
        # Replace the old dropdown selection code
        updated_content = re.sub(dropdown_selection_pattern, fixed_dropdown_code, updated_content)
        print("Enhanced dropdown selection logic")
    
    # 4. Add explicit version validation before comparing
    validate_pattern = r'if \(fromVersion && toVersion\) \{[\s\S]*?loadDiff\(fromVersion, toVersion\);[\s\S]*?\}'
    if re.search(validate_pattern, updated_content):
        validate_versions_code = """
    if (fromVersion && toVersion) {
        // Log the versions being compared
        console.log(`Comparing versions: ${fromVersion} → ${toVersion}`);
        
        // Validate versions
        fromVersion = fromVersion.toString().trim();
        toVersion = toVersion.toString().trim();
        
        // Reload versions if needed
        if (!fromVersion || !toVersion) {
            console.error('Invalid version selection');
            return;
        }
        
        loadDiff(fromVersion, toVersion);
    }
"""
        # Replace all instances of this pattern
        updated_content = re.sub(validate_pattern, validate_versions_code, updated_content)
        print("Added explicit version validation")
    
    # Write the modified content back
    with open(js_file_path, 'w') as f:
        f.write(updated_content)
    
    print("Fixed diff viewer version selection issues")
    return True

if __name__ == "__main__":
    if fix_diff_selections():
        print("\nDiff version selection fix applied successfully!")
    else:
        print("\nFailed to apply diff version selection fix. Please check the error messages above.")
