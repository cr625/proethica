#!/usr/bin/env python3
"""
Script to update the CLAUDE.md file with information about the repository cleanup.
"""

import os
from datetime import datetime
import re

def update_claude_md():
    """Update the CLAUDE.md file with today's repository cleanup information"""
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
    
    # Create new entry content
    new_entry = f"""
## {today} - Root Directory Cleanup

### Actions Taken

1. **Moved Utility Scripts to scripts/ Directory**
   - Moved reusable utility scripts from root directory to the scripts directory:
     - fix_ontology_automatically.py - Script to repair common syntax errors in ontology content
     - fix_ontology_syntax.py - Script to fix Turtle syntax issues in ontologies
     - fix_ontology_validation.py - Script to fix validation-related issues in the system

2. **Removed One-time Fix and Update Scripts**
   - Removed various one-time scripts whose changes have already been applied:
     - update_claude_md_with_navbar.py - One-time documentation update
     - update_claude_md.py - One-time documentation update
     - update_engineering_capability.py - References old .ttl files and fixes have been applied
     - update_ontology_with_capability.py - References old .ttl files
     - update_nav_bar.py - One-time navigation bar update
     - update_world_navbar.py - One-time world navigation bar update
     - update_ontology_editor.py - One-time editor update that's been completed
     - fix_mcp_entity_extraction.py - One-time MCP fix that's been applied
     - fix_ontology_editor_entity_link.py - One-time fix documented in CLAUDE.md
     - fix_ontology_editor_url_update.js - JavaScript fix that's been applied

3. **Created Repository Cleanup Script**
   - Added `scripts/cleanup_repository.py` to automate the cleanup process
   - Script logs all actions to a timestamped log file
   - Script creates backups of any files before moving/replacing them
   - Added `scripts/document_repository_cleanup.py` to document the cleanup

### Benefits

- Cleaner root directory with fewer unused scripts
- Better organization with reusable utility scripts in the scripts directory
- Better documentation of which fixes have already been applied
- Easier navigation of the codebase for new developers

### Implementation Details

The cleanup process moved useful general-purpose scripts to the scripts directory while
removing one-time fix scripts whose changes have already been applied to the codebase.
This helps maintain a cleaner project structure and prevents confusion about which fixes
have already been implemented.

### Next Steps

- Consider adding script categorization within the scripts directory
- Review and update docs/scripts_guide.md with new script locations
- Consider implementing a script review policy to prevent accumulation of one-time fix scripts
"""
    
    # Check if today's entry already exists
    date_pattern = re.compile(rf"## {today} -")
    if date_pattern.search(content):
        # If there's already an entry for today, append to it using an updating approach
        sections = re.split(r'(?=## \d{4}-\d{2}-\d{2})', content)
        updated_content = ""
        
        for section in sections:
            if section.startswith(f"## {today}"):
                # Check if the entry already has cleanup information
                if "Root Directory Cleanup" in section:
                    print("Entry about repository cleanup already exists for today")
                    return False
                # Add our cleanup as a new heading in today's entry
                section += "\n\n### Root Directory Cleanup\n"
                section += "\nReorganized scripts in the repository:\n"
                section += "\n1. **Moved Utility Scripts to scripts/ Directory**"
                section += "\n   - Moved reusable utility scripts from root directory to scripts/"
                section += "\n2. **Removed One-time Fix and Update Scripts**"
                section += "\n   - Removed various scripts whose changes have already been applied"
                section += "\n3. **Created Repository Cleanup Script**"
                section += "\n   - Added scripts for cleanup and documentation"
            updated_content += section
        
        with open(claude_md_path, 'w') as f:
            f.write(updated_content)
    else:
        # Otherwise, add new entry at the top
        updated_content = new_entry + content
        with open(claude_md_path, 'w') as f:
            f.write(updated_content)
    
    print(f"Updated {claude_md_path} with repository cleanup information")
    return True

if __name__ == "__main__":
    print("Updating CLAUDE.md with repository cleanup information...")
    update_claude_md()
    print("Done!")
