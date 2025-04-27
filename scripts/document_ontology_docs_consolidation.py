#!/usr/bin/env python3
"""
Script to update the CLAUDE.md file with information about the ontology documentation consolidation.
"""

import os
from datetime import datetime
import re

def update_claude_md():
    """Update the CLAUDE.md file with information about the ontology documentation consolidation"""
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
## {today} - Ontology Documentation Consolidation

### Actions Taken

1. **Consolidated Ontology Documentation**
   - Removed redundant and outdated ontology documentation files
   - Consolidated documentation into a single comprehensive guide
   - Added clear reference to the primary documentation in CLAUDE.md
   - Documented all database-driven ontology features in one place

2. **Files Removed**
   - Deprecated `docs/ontology_file_migration_guide.md` - Historical guide for file to database migration
   - Redundant `docs/ontology_database_storage.md` - Content now in comprehensive guide
   - Duplicate `docs/ontology_system.md` - Content now in comprehensive guide
   - Obsolete `ontology_editor_improvements.md` - Improvements have been implemented
   - One-time `ontology_fix_instructions.md` - Instructions for fixes that are now complete
   - Historical `ontology_update_report.md` - One-time update report no longer needed

3. **Primary Documentation**
   - `docs/ontology_comprehensive_guide.md` - Complete documentation with all features
   - This guide now contains information on:
     - Database-driven architecture
     - Entity types and hierarchies
     - Ontology structure
     - MCP integration
     - Best practices for ontology management
     - Troubleshooting and common issues

### Benefits

- Cleaner documentation structure with a single source of truth
- Better organization of ontology system knowledge
- Removal of references to deprecated file-based storage
- Clear indication of which documentation is current and relevant
- Simpler onboarding for new developers

### Implementation Details

Files removed were first backed up to the docs/archive directory for historical reference.
The comprehensive guide was updated to include all relevant information from multiple sources
and remove any references to outdated components (like file-based ontology storage).

### Next Steps

- Consider adding more examples of entity relationships
- Add diagrams showing the ontology structure and hierarchy
- Include screenshots of the entity editor for additional clarity
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
                if "Ontology Documentation Consolidation" in section:
                    print("Entry about ontology documentation consolidation already exists for today")
                    return False
                # Add our consolidation info as a new heading in today's entry
                section += "\n\n### Ontology Documentation Consolidation\n"
                section += "\nStreamlined ontology documentation:\n"
                section += "\n1. **Consolidated Documentation**"
                section += "\n   - Unified all ontology documentation into a single comprehensive guide"
                section += "\n2. **Removed Redundant Files**"
                section += "\n   - Archived outdated ontology documentation files"
                section += "\n3. **Added Documentation Index**"
                section += "\n   - Created clear reference to primary documentation in CLAUDE.md"
            updated_content += section
        
        with open(claude_md_path, 'w') as f:
            f.write(updated_content)
    else:
        # Otherwise, add new entry at the top
        updated_content = new_entry + content
        with open(claude_md_path, 'w') as f:
            f.write(updated_content)
    
    print(f"Updated {claude_md_path} with ontology documentation consolidation information")
    return True

if __name__ == "__main__":
    print("Updating CLAUDE.md with ontology documentation consolidation information...")
    update_claude_md()
    print("Done!")
