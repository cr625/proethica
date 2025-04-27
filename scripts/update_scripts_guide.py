#!/usr/bin/env python3
"""
Script to update the scripts_guide.md with information about the moved scripts
and the cleanup scripts that have been added.
"""

import os
from datetime import datetime

def update_scripts_guide():
    """Update the scripts_guide.md file with info about moved scripts"""
    scripts_guide_path = "docs/scripts_guide.md"
    
    # Check if file exists
    if not os.path.exists(scripts_guide_path):
        print(f"Error: {scripts_guide_path} does not exist")
        return False
    
    # Read the current file content
    with open(scripts_guide_path, 'r') as f:
        content = f.read()
    
    # Check if scripts are already documented
    if "fix_ontology_automatically.py" in content and "cleanup_repository.py" in content:
        print("Scripts are already documented in the guide")
        return False
    
    # Find System Maintenance section to add our entry
    system_maintenance_section = "## System Maintenance"
    if system_maintenance_section not in content:
        print(f"Error: Could not find '{system_maintenance_section}' section")
        return False
    
    # Position after the section header (after the first entry in this section)
    section_start = content.find(system_maintenance_section)
    first_line_end = content.find('\n', section_start)
    
    if section_start == -1 or first_line_end == -1:
        print("Error: Could not locate the proper position to add new entries")
        return False
    
    # New entries to add
    new_entries = """
- **cleanup_repository.py**: Cleans up the root directory by moving utility scripts to scripts/ and removing one-time fixes.
- **document_repository_cleanup.py**: Updates CLAUDE.md with information about repository cleanup.
- **update_scripts_guide.py**: Updates the scripts guide with new script entries.
"""
    
    # Find Ontology Management section to add moved scripts
    ontology_management_section = "## Ontology Management"
    if ontology_management_section not in content:
        print(f"Error: Could not find '{ontology_management_section}' section")
        return False
    
    # Position after the section header
    ont_section_start = content.find(ontology_management_section)
    ont_first_line_end = content.find('\n', ont_section_start)
    
    if ont_section_start == -1 or ont_first_line_end == -1:
        print("Error: Could not locate the proper position to add ontology entries")
        return False
    
    # Moved script entries
    moved_entries = """
- **fix_ontology_automatically.py**: Automatically fixes syntax errors in ontology content stored in the database.
- **fix_ontology_syntax.py**: Fixes Turtle syntax issues in ontologies with targeted repairs.
- **fix_ontology_validation.py**: Fixes validation-related issues in the ontology editor.
"""
    
    # Insert the new entries
    updated_content = (
        content[:first_line_end + 1] + 
        new_entries + 
        content[first_line_end + 1:ont_first_line_end + 1] +
        moved_entries +
        content[ont_first_line_end + 1:]
    )
    
    # Write the updated content back to the file
    with open(scripts_guide_path, 'w') as f:
        f.write(updated_content)
    
    print(f"Updated {scripts_guide_path} with new script entries")
    return True

if __name__ == "__main__":
    print("Updating scripts guide with new script entries...")
    update_scripts_guide()
    print("Done!")
