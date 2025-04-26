#!/usr/bin/env python3
"""
Script to update CLAUDE.md with information about the ontology version loading fix.
"""
import os
import sys
from datetime import datetime

def update_claude_md():
    """
    Update the CLAUDE.md file with information about the ontology version loading fix.
    """
    print("Updating CLAUDE.md with ontology version loading fix information...")
    
    # Get current date in YYYY-MM-DD format
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Create content to add
    new_content = f"""
## {today} - Ontology Version Loading Fix

### Implemented Changes

1. **Fixed Ontology Version Loading in Editor**
   - Fixed issue where clicking on version numbers resulted in "Error loading version: Failed to load version"
   - Updated editor.js to use the correct version API endpoint format
   - Modified version request to include both ontology ID and version number
   - Resolved 500 errors when trying to load previous versions

2. **Updated Version List Generation**
   - Modified updateVersionsList function to include version_number as a data attribute
   - Updated version click handler to pass version number instead of version ID
   - Maintained backward compatibility with existing version handling

3. **Enhanced API Endpoint Utilization**
   - Switched from `/ontology-editor/api/versions/${{versionId}}` endpoint to:
   - `/ontology-editor/api/versions/${{currentOntologyId}}/${{versionNumber}}` endpoint
   - Properly utilized the existing API endpoint that was already implemented
   - Fixed parameter alignment between frontend and backend

### Implementation Details
- Created `scripts/fix_ontology_version_loading.py` for automated JavaScript fixes
- Used precise regex pattern matching to locate and modify only affected code sections
- Created backup at `editor.js.version_loading.bak` before applying changes
- Fixed three distinct areas of the code to ensure complete functionality:
  1. Version list generation to include version numbers
  2. Click handler logic to use version numbers
  3. Fetch URL format in the loadVersion function

### Benefits
- Restored ability to view previous versions of ontologies
- Eliminated error messages when clicking on version numbers
- Removed 500 errors in the browser console
- Improved user experience by enabling full version history browsing
- Better aligned frontend code with backend API implementation

### Verification Steps
1. Loaded the ontology editor and confirmed all versions were visible
2. Clicked on various version numbers and verified they loaded successfully
3. Checked browser console to confirm no error messages
4. Ensured version highlighting worked correctly in the Version list

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
