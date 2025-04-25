#!/usr/bin/env python3
"""
Script to update the CLAUDE.md file with information about the
ontology editor improvements implemented today.
"""

import os
from datetime import datetime
import re

def update_claude_md():
    """Update the CLAUDE.md file with today's improvements"""
    claude_md_path = "CLAUDE.md"
    
    # Check if file exists
    if not os.path.exists(claude_md_path):
        print(f"Error: {claude_md_path} does not exist")
        return False
    
    # Read the current file content
    with open(claude_md_path, 'r') as f:
        content = f.read()
    
    # Get today's date in YYYY-MM-DD format
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Create new entry with today's date
    new_entry = f"""
## {today} - Ontology Editor Improvements

### Fixes Implemented

1. **Fixed Entity Extraction in Ontology Editor**
   - Created a direct database-based entity extraction approach
   - Modified the ontology editor API to use the same entity extraction service as the world detail page
   - Eliminated dependency on the MCP server for entity extraction
   - Ensured consistent entity display between world detail page and ontology editor

2. **Improved URL Management in Ontology Editor**
   - Updated the ontology editor to properly update the URL when switching between ontologies
   - Added browser history support for better navigation
   - Preserved view parameters for consistent user experience
   - Enabled proper sharing of links to specific ontologies

3. **Fixed Ontology Validation**
   - Modified how ontology content is sent for validation to prevent parsing errors
   - Updated backend validation route to properly handle JSON data
   - Improved error handling and debugging for validation issues
   - Enhanced error messages to better identify syntax errors in ontologies

### Benefits

- More reliable entity extraction without HTTP call dependency
- Consistent experience between different parts of the application
- Better navigation through proper URL management
- Improved validation process for ontology development

### Files Modified

- `ontology_editor/api/routes.py`
- `ontology_editor/static/js/editor.js`
- `app/services/ontology_entity_service.py`

### Next Steps

- Consider adding syntax highlighting for ontology errors in the editor
- Implement more detailed validation feedback with line numbers and error locations
- Explore automatic syntax fixing options for common ontology errors
"""
    
    # Check if today's date already exists in the file
    date_pattern = re.compile(rf"## {today} - ")
    if date_pattern.search(content):
        # If today's date exists, append to that entry
        sections = re.split(r'(?=## \d{4}-\d{2}-\d{2})', content)
        
        updated_content = ""
        for section in sections:
            if section.startswith(f"## {today}"):
                # Replace this section with new entry
                updated_content += new_entry
            else:
                updated_content += section
    else:
        # Otherwise, add new entry at the top
        updated_content = new_entry + content
    
    # Write the updated content back to the file
    with open(claude_md_path, 'w') as f:
        f.write(updated_content)
    
    print(f"Updated {claude_md_path} with today's improvements")
    return True

if __name__ == "__main__":
    print("Updating CLAUDE.md with ontology editor improvements...")
    update_claude_md()
    print("Done!")
