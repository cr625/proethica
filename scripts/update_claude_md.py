#!/usr/bin/env python3
"""
Script to update CLAUDE.md with information about the ontology name and domain ID update.
"""
import os
import sys
from datetime import datetime

def update_claude_md():
    """
    Update the CLAUDE.md file with information about the ontology update.
    """
    print("Updating CLAUDE.md with ontology update information...")
    
    # Get current date in YYYY-MM-DD format
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Create content to add
    new_content = f"""
## {today} - Ontology Name and Domain ID Update

### Implemented Changes

1. **Updated Ontology Name and Domain ID**
   - Changed ontology name from "Engineering Ethics Nspe Extended" to "Engineering Ethics"
   - Changed domain ID from "engineering-ethics-nspe-extended" to "engineering-ethics"
   - Updated to match the ontology prefix declaration `@prefix : engineering-ethics`
   - Ensured consistent naming across the database and application

2. **Updated World References**
   - Modified World ID 1 ("Engineering") to use the new domain_id
   - Updated the ontology_source field to maintain proper entity access
   - Restarted the MCP server to ensure it recognized the domain ID change
   - Verified entity access through the MCP client

### Implementation Details
- Created `scripts/check_ontology_id_1.py` to examine current ontology state
- Created `scripts/update_ontology_id_1.py` to perform the database update
- Created `scripts/verify_world_ontology_access.py` to verify world-ontology connections
- Created `scripts/restart_mcp_server.py` to restart the MCP server to recognize changes
- Created `scripts/verify_mcp_entities.py` to verify entity access post-update
- Created `scripts/ontology_update_report.py` to document the changes

### Benefits
- Improved consistency between ontology prefix declaration and database records
- Enhanced stability of entity references with matching domain ID and prefix
- Better alignment with best practices for ontology naming
- More intuitive ontology name focusing on the domain (Engineering Ethics)
- Eliminated potential confusion from mismatched domain ID and prefix

### Verification Steps
1. Confirmed ontology record was successfully updated in the database
2. Verified world references were updated to use the new domain ID
3. Restarted MCP server to ensure changes were recognized
4. Confirmed MCP client could retrieve entities from the updated ontology

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
