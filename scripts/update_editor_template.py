#!/usr/bin/env python3
"""
Script to update the editor.html template to add the diff viewer functionality.
"""
import os
import re
import sys

def update_editor_template():
    """
    Update the editor.html template to include the diff viewer functionality.
    """
    # Path to the template file
    template_file_path = 'ontology_editor/templates/editor.html'
    
    # Check if the file exists
    if not os.path.exists(template_file_path):
        print(f"Error: {template_file_path} not found")
        return False
    
    # Create backup
    backup_file_path = f'{template_file_path}.diff_viewer.bak'
    print(f"Creating backup of {template_file_path} to {backup_file_path}")
    
    with open(template_file_path, 'r') as f:
        original_content = f.read()
        
    with open(backup_file_path, 'w') as f:
        f.write(original_content)
    
    # 1. Add the CSS link in the head section
    if '<link rel="stylesheet" href="{{ url_for(\'ontology_editor.static\', filename=\'css/editor.css\') }}">' in original_content:
        updated_content = original_content.replace(
            '<link rel="stylesheet" href="{{ url_for(\'ontology_editor.static\', filename=\'css/editor.css\') }}">',
            '<link rel="stylesheet" href="{{ url_for(\'ontology_editor.static\', filename=\'css/editor.css\') }}">\n    <link rel="stylesheet" href="{{ url_for(\'ontology_editor.static\', filename=\'css/diff.css\') }}">'
        )
    else:
        print("Could not find the editor.css link in the template.")
        return False
    
    # 2. Add the diff.js script at the end of the body
    if '<script src="{{ url_for(\'ontology_editor.static\', filename=\'js/editor.js\') }}"></script>' in updated_content:
        updated_content = updated_content.replace(
            '<script src="{{ url_for(\'ontology_editor.static\', filename=\'js/editor.js\') }}"></script>',
            '<script src="{{ url_for(\'ontology_editor.static\', filename=\'js/editor.js\') }}"></script>\n    <script src="{{ url_for(\'ontology_editor.static\', filename=\'js/diff.js\') }}"></script>'
        )
    else:
        print("Could not find the editor.js script tag in the template.")
        return False
    
    # 3. Add the diff modal HTML before the closing body tag
    diff_modal_html = """
    <!-- Diff Modal -->
    <div class="modal-backdrop" id="diffModalBackdrop"></div>
    <div class="diff-modal" id="diffModal">
        <div class="diff-modal-dialog">
            <div class="diff-modal-content">
                <div class="diff-modal-header">
                    <h5 class="diff-modal-title">Compare Versions</h5>
                    <button type="button" class="close" id="closeDiffBtn" aria-label="Close">
                        <span aria-hidden="true">&times;</span>
                    </button>
                </div>
                <div class="diff-modal-body">
                    <div class="row mb-3">
                        <div class="col-md-6">
                            <div class="version-metadata">
                                <h6>From Version:</h6>
                                <p id="diffFromInfo">Loading...</p>
                                <div id="diffFromCommitSection" style="display: none;">
                                    <p class="mb-1">Commit message:</p>
                                    <div class="commit-message" id="diffFromCommit"></div>
                                </div>
                            </div>
                            <div class="form-group">
                                <label for="diffFromVersion">Select from version:</label>
                                <select class="form-control" id="diffFromVersion"></select>
                            </div>
                        </div>
                        <div class="col-md-6">
                            <div class="version-metadata">
                                <h6>To Version:</h6>
                                <p id="diffToInfo">Loading...</p>
                                <div id="diffToCommitSection" style="display: none;">
                                    <p class="mb-1">Commit message:</p>
                                    <div class="commit-message" id="diffToCommit"></div>
                                </div>
                            </div>
                            <div class="form-group">
                                <label for="diffToVersion">Select to version:</label>
                                <select class="form-control" id="diffToVersion"></select>
                            </div>
                        </div>
                    </div>
                    
                    <div class="mb-3">
                        <div class="d-flex align-items-center">
                            <span class="format-label">Unified</span>
                            <label class="switch mx-2">
                                <input type="checkbox" id="diffFormatToggle">
                                <span class="slider"></span>
                            </label>
                            <span class="format-label">Side-by-side</span>
                        </div>
                    </div>
                    
                    <div id="diffContent" class="border rounded p-3 bg-light">
                        <div class="text-center py-5">
                            <p>Select versions to compare</p>
                        </div>
                    </div>
                </div>
                <div class="diff-modal-footer">
                    <button type="button" class="btn btn-secondary" id="closeDiffBtnFooter">Close</button>
                </div>
            </div>
        </div>
    </div>
    """
    
    # Insert the diff modal before the closing body tag
    if '</body>' in updated_content:
        updated_content = updated_content.replace('</body>', diff_modal_html + '\n</body>')
    else:
        print("Could not find the closing body tag in the template.")
        return False
    
    # Write the updated content back
    with open(template_file_path, 'w') as f:
        f.write(updated_content)
    
    print(f"Successfully updated {template_file_path} to include diff viewer functionality")
    print("\nChanges made:")
    print("1. Added diff.css link in the head section")
    print("2. Added diff.js script at the end of the body")
    print("3. Added diff modal HTML before the closing body tag")
    
    return True

if __name__ == "__main__":
    if update_editor_template():
        print("\nTemplate update successful!")
    else:
        print("\nFailed to update template. Please check the error messages above.")
