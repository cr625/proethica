#!/usr/bin/env python3
"""
Script to clean up the root directory by:
1. Moving useful utility scripts to the scripts directory
2. Removing one-time fix and update scripts that are no longer needed
"""

import os
import shutil
from datetime import datetime
import sys

# Create a cleanup log file
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = f"cleanup_log_{TIMESTAMP}.txt"

# Files to move to scripts directory (still potentially useful)
FILES_TO_MOVE = [
    "fix_ontology_automatically.py",
    "fix_ontology_syntax.py",
    "fix_ontology_validation.py"
]

# Files to remove (one-time updates that have been completed)
FILES_TO_REMOVE = [
    "update_claude_md_with_navbar.py",
    "update_claude_md.py",
    "update_engineering_capability.py",
    "update_ontology_with_capability.py",
    "update_nav_bar.py",
    "update_world_navbar.py",
    "update_ontology_editor.py",
    "fix_mcp_entity_extraction.py",
    "fix_ontology_editor_entity_link.py",
    "fix_ontology_editor_url_update.js"
]

def log_message(message):
    """Write message to log file and print to console"""
    print(message)
    with open(LOG_FILE, 'a') as log:
        log.write(message + "\n")

def main():
    """Main function to clean up the repository"""
    log_message(f"Starting repository cleanup at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_message("="*80)
    
    # Make sure scripts directory exists
    if not os.path.exists("scripts"):
        log_message("Error: scripts directory does not exist. Aborting.")
        return False
    
    # Track what we've done
    moved_files = []
    removed_files = []
    skipped_files = []
    
    # First, move files to scripts directory
    log_message("\n== Moving files to scripts directory ==")
    for file_name in FILES_TO_MOVE:
        if os.path.exists(file_name):
            # Check if file already exists in scripts directory
            dest_path = os.path.join("scripts", file_name)
            if os.path.exists(dest_path):
                backup_name = f"{dest_path}.{TIMESTAMP}.bak"
                log_message(f"File already exists at {dest_path}, creating backup: {backup_name}")
                shutil.copy2(dest_path, backup_name)
            
            # Move the file
            try:
                shutil.move(file_name, dest_path)
                log_message(f"✓ Moved: {file_name} -> {dest_path}")
                moved_files.append(file_name)
            except Exception as e:
                log_message(f"✗ Error moving {file_name}: {str(e)}")
                skipped_files.append(file_name)
        else:
            log_message(f"✗ Skipped (not found): {file_name}")
            skipped_files.append(file_name)
    
    # Then, remove files
    log_message("\n== Removing unnecessary files ==")
    for file_name in FILES_TO_REMOVE:
        if os.path.exists(file_name):
            try:
                os.remove(file_name)
                log_message(f"✓ Removed: {file_name}")
                removed_files.append(file_name)
            except Exception as e:
                log_message(f"✗ Error removing {file_name}: {str(e)}")
                skipped_files.append(file_name)
        else:
            log_message(f"✗ Skipped (not found): {file_name}")
            skipped_files.append(file_name)
    
    # Summarize what we did
    log_message("\n== Summary ==")
    log_message(f"Files moved to scripts directory: {len(moved_files)}")
    for file in moved_files:
        log_message(f"  - {file}")
    
    log_message(f"\nFiles removed: {len(removed_files)}")
    for file in removed_files:
        log_message(f"  - {file}")
    
    log_message(f"\nFiles skipped: {len(skipped_files)}")
    for file in skipped_files:
        log_message(f"  - {file}")
    
    log_message("\nNotes:")
    log_message("1. Files moved to the scripts directory are general utilities that may be useful for future maintenance.")
    log_message("2. Files removed were one-time fixes or updates that have already been applied.")
    log_message("3. A log of all actions has been saved to: " + LOG_FILE)
    
    return True

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)
