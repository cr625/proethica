#!/usr/bin/env python3
"""
Script to update the CLAUDE.md file with information about the MCP and ontology scripts organization.
"""

import os
from datetime import datetime
import re

def update_claude_md():
    """Update the CLAUDE.md file with MCP and ontology scripts organization information"""
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
## {today} - MCP and Ontology Scripts Organization

### Actions Taken

1. **Organized MCP and Ontology Scripts**
   - Moved all MCP and ontology related utility scripts from the root directory to the scripts directory
   - Ensured consistent organization of debugging and maintenance tools
   - Simplified root directory structure
   - Scripts remain accessible for diagnostics and troubleshooting

2. **Files Organized**
   - `check_world.py` - Simple utility to check world configuration
   - `check_ontology.py` - Utility to verify ontology existence in database
   - `debug_entity_extraction.py` - Diagnostic tool for entity extraction issues
   - `debug_mcp_server.py` - Tool to debug the MCP server functionality
   - `direct_fix_mcp_server.py` - MCP server fix utility
   - `document_ontology_entity_update.py` - Documentation tool for ontology entity updates
   - `export_fix_import_ontology.py` - Utility for ontology export, fix, and import workflow
   - `final_fix_ontology.py` - Final ontology fix utility
   - `mcp_client_debug.py` - MCP client debugging tool
   - `verify_ontology_consistency.py` - Ontology consistency verification tool

3. **Documentation**
   - Updated scripts guide to reflect new script locations
   - Created organized structure for all diagnostic and maintenance tools
   - Preserved tool functionality while improving repository organization

### Benefits

- Cleaner root directory structure
- Better organization of diagnostic and maintenance tools
- Preserved all tool functionality with logical organization
- Simplified navigation for developers
- Consistent approach to repository structure

### Implementation Details

The tool organization process:
1. Identified MCP and ontology related utility scripts in the root directory
2. Created backups of any existing scripts in the destination directory
3. Moved scripts to the scripts directory with proper logging
4. Generated a cleanup log with details of all organizational changes

### Next Steps

- Consider adding additional documentation for these diagnostic tools
- Group related scripts into subdirectories by functionality
- Review script usage patterns to identify further organizational improvements
"""
    
    # Check if today's entry already exists
    date_pattern = re.compile(rf"## {today} -")
    if date_pattern.search(content):
        # If there's already an entry for today, append to it using an updating approach
        sections = re.split(r'(?=## \d{4}-\d{2}-\d{2})', content)
        updated_content = ""
        
        for section in sections:
            if section.startswith(f"## {today}"):
                # Check if the entry already has organization information
                if "MCP and Ontology Scripts Organization" in section:
                    print("Entry about MCP and ontology scripts organization already exists for today")
                    return False
                # Add our organization info as a new heading in today's entry
                section += "\n\n### MCP and Ontology Scripts Organization\n"
                section += "\nOrganized diagnostic and utility tools:\n"
                section += "\n1. **Moved Diagnostic Tools**"
                section += "\n   - Relocated all MCP and ontology debugging scripts to scripts directory"
                section += "\n2. **Preserved Functionality**"
                section += "\n   - All diagnostic and maintenance capabilities remain available"
                section += "\n3. **Simplified Structure**"
                section += "\n   - Cleaner root directory with improved organization"
            updated_content += section
        
        with open(claude_md_path, 'w') as f:
            f.write(updated_content)
    else:
        # Otherwise, add new entry at the top
        updated_content = new_entry + content
        with open(claude_md_path, 'w') as f:
            f.write(updated_content)
    
    print(f"Updated {claude_md_path} with MCP and ontology scripts organization information")
    return True

if __name__ == "__main__":
    print("Updating CLAUDE.md with MCP and ontology scripts organization information...")
    update_claude_md()
    print("Done!")
