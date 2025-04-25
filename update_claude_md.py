#!/usr/bin/env python3
"""
Script to update the CLAUDE.md file with details of the ontology entity extraction fix.
"""
from datetime import datetime
import os
import re

def update_claude_md():
    """Update the CLAUDE.md file with information about the ontology entity display fix."""
    
    # Path to CLAUDE.md
    claude_md_path = os.path.join(os.getcwd(), "CLAUDE.md")
    
    # Today's date
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Read the existing content
    try:
        with open(claude_md_path, 'r') as f:
            content = f.read()
    except FileNotFoundError:
        content = "# CLAUDE.md - Project Work Log\n\n"
    
    # Create the new entry
    new_entry = f"""## {today} - Fixed Ontology Entity Extraction and Display

### Changes Made:
- Created a new service `OntologyEntityService` that directly extracts entities from ontologies stored in the database 
- Modified the world detail view to use the new service instead of the MCP server for entity extraction
- Implemented entity extraction functions that properly handle different namespaces and entity types
- Added caching to improve performance when retrieving the same ontology multiple times

### Technical Details:
- The new service parses the ontology content with RDFLib and extracts entities of different types
- It handles both domain-specific namespaces and the intermediate namespace
- It properly identifies entity instances that have both `EntityType` and specific type declarations
- The world details page now displays all entities correctly

### Benefits:
- More reliable entity extraction independent of MCP server issues
- Simplified code path with direct database access instead of HTTP calls
- Better error handling and logging for ontology parsing issues
- Performance improvements through caching

### Next Steps:
- Continue testing with different ontologies to ensure all entity types are properly extracted
- Consider adding more detailed error messages for ontology syntax validation
- Review the ontology editor to ensure it produces valid syntax for entity definitions
"""
    
    # Check if today's date is already in the file
    if f"## {today}" in content:
        # Replace the existing entry for today
        pattern = f"## {today}.*?(?=^## |\Z)"
        new_content = re.sub(pattern, new_entry, content, flags=re.DOTALL | re.MULTILINE)
    else:
        # Add the new entry at the top, after any headers
        header_end = content.find("\n\n")
        if header_end == -1:
            # No clear header, just add at the top
            new_content = content + "\n\n" + new_entry
        else:
            # Add after the header
            new_content = content[:header_end+2] + new_entry + "\n\n" + content[header_end+2:]
    
    # Write the updated content back to the file
    with open(claude_md_path, 'w') as f:
        f.write(new_content)
    
    print(f"Updated {claude_md_path} with information about the ontology entity extraction fix.")

if __name__ == "__main__":
    update_claude_md()
