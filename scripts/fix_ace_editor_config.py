#!/usr/bin/env python
"""
Fix the ACE editor configuration by rewriting the initializeEditor function
"""
import os
import re

def fix_ace_editor_config():
    """
    Find and replace the initializeEditor function to use setOption instead of setOptions
    """
    js_file_path = 'ontology_editor/static/js/editor.js'
    if not os.path.exists(js_file_path):
        print(f"Error: {js_file_path} not found")
        return False
    
    # Create backup with a clear name
    backup_file_path = 'ontology_editor/static/js/editor.js.ace_config.bak'
    print(f"Creating backup of {js_file_path} to {backup_file_path}")
    with open(js_file_path, 'r') as f:
        original_content = f.read()
    
    with open(backup_file_path, 'w') as f:
        f.write(original_content)
    
    # The corrected initializeEditor function
    new_init_function = '''/**
 * Initialize the ACE editor
 */
function initializeEditor() {
    editor = ace.edit("editor");
    editor.setTheme("ace/theme/monokai");
    editor.session.setMode("ace/mode/turtle");
    editor.setShowPrintMargin(false);
    
    // Set options individually to avoid naming issues
    editor.setOption("enableBasicAutocompletion", true);
    editor.setOption("enableLiveAutocompletion", true);
    editor.setOption("fontSize", "14px");
    editor.setOption("tabSize", 2);
    
    // Track changes to enable/disable save button
    editor.getSession().on('change', function() {
        if (!isEditorDirty && currentOntologyId) {
            isEditorDirty = true;
            document.getElementById('saveBtn').disabled = false;
        }
    });
}'''
    
    # Find the initializeEditor function and replace it
    pattern = re.compile(r'/\*\*\s*\n\s*\*\s*Initialize the ACE editor[\s\S]*?function initializeEditor\(\)[\s\S]*?\}\s*\n')
    
    if not pattern.search(original_content):
        print("Could not find the initializeEditor function")
        return False
    
    modified_content = pattern.sub(new_init_function + '\n\n', original_content)
    
    # Write the modified content back to the file
    with open(js_file_path, 'w') as f:
        f.write(modified_content)
    
    print("Successfully updated ACE editor configuration")
    return True

if __name__ == "__main__":
    if fix_ace_editor_config():
        print("ACE editor configuration fixed")
    else:
        print("Failed to fix ACE editor configuration")
