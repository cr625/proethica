#!/usr/bin/env python3
"""
Script to consolidate ontology documentation files in the repository.
This script:
1. Removes redundant and outdated documentation files
2. Moves relevant files from the root directory to docs/
3. Updates CLAUDE.md with a reference to the primary ontology documentation
"""

import os
import shutil
import re
import sys
from datetime import datetime

# List of files to remove (outdated or redundant)
FILES_TO_REMOVE = [
    "docs/ontology_file_migration_guide.md",  # Explicitly marked as deprecated
    "docs/ontology_database_storage.md",      # Content covered in comprehensive guide
    "docs/ontology_system.md",               # Content covered in comprehensive guide
    "ontology_editor_improvements.md",        # Historical improvements that have been implemented
    "ontology_fix_instructions.md",           # One-time fix instructions that are no longer needed
    "ontology_update_report.md"               # One-time update report that is now historical
]

# Files to keep or consolidate
PRIMARY_DOC = "docs/ontology_comprehensive_guide.md"

# Log file
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = f"ontology_docs_cleanup_log_{TIMESTAMP}.txt"

def log_message(message):
    """Write message to log file and print to console"""
    print(message)
    with open(LOG_FILE, 'a') as log:
        log.write(message + "\n")

def update_claude_md_with_ontology_index():
    """Update CLAUDE.md with a reference to the primary ontology documentation"""
    claude_md_path = "CLAUDE.md"
    
    if not os.path.exists(claude_md_path):
        log_message(f"Error: {claude_md_path} does not exist")
        return False
    
    # Read the current file content
    with open(claude_md_path, 'r') as f:
        content = f.read()
    
    # Check if there's already an ontology documentation index
    if "## Ontology Documentation" in content:
        log_message("Ontology documentation index already exists in CLAUDE.md")
        return True
    
    # Get today's date in YYYY-MM-DD format
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Find the most recent entry to add our index after it
    date_pattern = re.compile(r"## \d{4}-\d{2}-\d{2}")
    matches = list(date_pattern.finditer(content))
    
    if not matches:
        log_message("Error: Could not find a date entry in CLAUDE.md")
        return False
    
    most_recent_entry = matches[0]
    next_entry_match = None
    
    if len(matches) > 1:
        next_entry_match = matches[1]
    
    # Find the position to insert our index
    if next_entry_match:
        # Insert before the second entry
        insert_pos = next_entry_match.start()
    else:
        # Insert at the beginning of the file
        insert_pos = 0
    
    # Create the ontology documentation index
    ontology_index = f"""
## Ontology Documentation

The ProEthica system uses a database-driven ontology system to define entity types
(roles, conditions, resources, actions, events, and capabilities) available in worlds.

### Primary Documentation

- [Comprehensive Ontology Guide](docs/ontology_comprehensive_guide.md): Complete documentation of the ontology system, including database storage, entity management, and best practices.

### Key Features

1. **Database-Driven Storage**: All ontologies are stored in the database with proper versioning
2. **Entity Editor**: Intuitive interface for managing ontology entities
3. **MCP Integration**: Ontologies are accessible to LLMs via the Model Context Protocol
4. **Hierarchy System**: Well-defined entity hierarchies with specialized parent classes
5. **Protection**: Base ontologies are protected from unauthorized modifications

For technical details, refer to the comprehensive guide above.

"""
    
    updated_content = content[:insert_pos] + ontology_index + content[insert_pos:]
    
    # Write the updated content back to the file
    with open(claude_md_path, 'w') as f:
        f.write(updated_content)
    
    log_message(f"Updated {claude_md_path} with ontology documentation index")
    return True

def remove_redundant_files():
    """Remove redundant and outdated documentation files"""
    removed_files = []
    skipped_files = []
    
    for file_path in FILES_TO_REMOVE:
        if os.path.exists(file_path):
            # Create a backup directory within docs for removed files
            backup_dir = os.path.join("docs", "archive")
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            # Copy to backup before removing
            file_name = os.path.basename(file_path)
            backup_path = os.path.join(backup_dir, f"{file_name}.{TIMESTAMP}.bak")
            try:
                shutil.copy2(file_path, backup_path)
                os.remove(file_path)
                log_message(f"✓ Removed {file_path} (backup: {backup_path})")
                removed_files.append(file_path)
            except Exception as e:
                log_message(f"✗ Error removing {file_path}: {str(e)}")
                skipped_files.append(file_path)
        else:
            log_message(f"✗ Skipped (not found): {file_path}")
            skipped_files.append(file_path)
    
    return removed_files, skipped_files

def main():
    """Main function to consolidate ontology documentation"""
    log_message(f"Starting ontology documentation cleanup at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_message("="*80)
    
    # Make sure the primary doc exists
    if not os.path.exists(PRIMARY_DOC):
        log_message(f"Error: Primary document {PRIMARY_DOC} does not exist. Aborting.")
        return False
    
    # Remove redundant files
    log_message("\n== Removing redundant and outdated files ==")
    removed_files, skipped_files = remove_redundant_files()
    
    # Update CLAUDE.md with a reference to the primary doc
    log_message("\n== Updating CLAUDE.md with ontology documentation index ==")
    claude_updated = update_claude_md_with_ontology_index()
    
    # Print summary
    log_message("\n== Summary ==")
    log_message(f"Files removed: {len(removed_files)}")
    for file in removed_files:
        log_message(f"  - {file}")
    
    log_message(f"\nFiles skipped: {len(skipped_files)}")
    for file in skipped_files:
        log_message(f"  - {file}")
    
    log_message(f"\nCLAUDE.md updated: {claude_updated}")
    
    log_message("\nNotes:")
    log_message("1. Removed files have been backed up to docs/archive/ directory")
    log_message("2. The primary ontology documentation is now docs/ontology_comprehensive_guide.md")
    log_message("3. CLAUDE.md has been updated with an index pointing to the ontology documentation")
    log_message("4. A log of all actions has been saved to: " + LOG_FILE)
    
    return True

if __name__ == "__main__":
    result = main()
    if result:
        print("\nOntology documentation consolidation complete!")
    else:
        print("\nOntology documentation consolidation failed. See log for details.")
    
    sys.exit(0 if result else 1)
