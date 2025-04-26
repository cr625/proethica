#!/usr/bin/env python3
"""
Script to update CLAUDE.md with information about the ontology diff viewer feature.
"""
import os
import sys
from datetime import datetime

def update_claude_md():
    """
    Update the CLAUDE.md file with information about the ontology diff viewer.
    """
    print("Updating CLAUDE.md with ontology diff viewer information...")
    
    # Get current date in YYYY-MM-DD format
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Create content to add
    new_content = f"""
## {today} - Ontology Version Diff Viewer Implementation

### Implemented Changes

1. **Added Version Comparison Functionality**
   - Implemented a new API endpoint for comparing ontology versions
   - Created a diff viewer UI for visualizing changes between versions
   - Added "Compare" buttons to version list items for easy access
   - Supported both unified and side-by-side diff views

2. **Backend Implementation**
   - Created `/versions/<int:ontology_id>/diff` API endpoint
   - Utilized Python's difflib for generating diffs
   - Supported two output formats: unified (text-based) and split (HTML table)
   - Added proper error handling and version metadata

3. **Frontend Implementation**
   - Developed a responsive modal interface for the diff viewer
   - Added version selection dropdowns for comparing any two versions
   - Implemented a toggle switch for switching between diff formats
   - Added version metadata display with commit messages

### Implementation Details
- Created `scripts/create_ontology_diff_endpoint.py` to add the backend API
- Created `ontology_editor/static/js/diff.js` for frontend functionality
- Created `ontology_editor/static/css/diff.css` for styling the diff viewer
- Created `scripts/update_editor_template.py` to update the editor template
- Used MutationObserver to dynamically add compare buttons to version list items
- Utilized difflib.unified_diff and difflib.HtmlDiff for generating diffs

### Benefits
- Improved ontology development workflow with version comparison
- Enabled easy identification of changes between versions
- Enhanced collaboration by making version differences clearly visible
- Made ontology evolution more transparent and trackable
- Improved debugging of ontology changes with visual diff

### How to Use
1. Open the ontology editor and load an ontology with multiple versions
2. Click the "Compare" button on any version in the version list
3. Select the versions to compare in the diff viewer modal
4. Toggle between unified and side-by-side views as needed
5. View detailed changes with highlighted additions, removals, and modifications

### Future Enhancements
- Add semantic diff option that understands RDF/Turtle syntax
- Implement highlighting for specific entity changes
- Add ability to export/save diff results
- Add filtering options to focus on specific types of changes

"""
    
    # Read the current CLAUDE.md file
    try:
        with open('CLAUDE.md', 'r') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading CLAUDE.md: {str(e)}")
        return False
    
    # Insert new content after the first line (title)
    lines = content.split('\n')
    if len(lines) < 2:
        # If file is too short, just prepend the new content
        new_full_content = lines[0] + "\n" + new_content + "\n" + "\n".join(lines[1:])
    else:
        new_full_content = lines[0] + "\n" + new_content + "\n" + "\n".join(lines[1:])
    
    # Write the updated content back
    try:
        with open('CLAUDE.md', 'w') as f:
            f.write(new_full_content)
        print("Successfully updated CLAUDE.md")
        return True
    except Exception as e:
        print(f"Error writing to CLAUDE.md: {str(e)}")
        return False

if __name__ == "__main__":
    update_claude_md()
