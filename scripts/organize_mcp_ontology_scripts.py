#!/usr/bin/env python3
"""
Script to clean up and organize MCP and ontology related scripts in the root directory
by moving them to the scripts directory.
"""

import os
import sys
import shutil
from datetime import datetime

# Create a log file
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = f"mcp_ontology_scripts_cleanup_log_{TIMESTAMP}.txt"

# Files to move to scripts directory (diagnostic and utility scripts)
MCP_ONTOLOGY_SCRIPTS = [
    "check_world.py",
    "check_ontology.py",
    "debug_entity_extraction.py",
    "debug_mcp_server.py",
    "direct_fix_mcp_server.py", 
    "document_ontology_entity_update.py",
    "export_fix_import_ontology.py",
    "final_fix_ontology.py",
    "mcp_client_debug.py",
    "verify_ontology_consistency.py"
]

def log_message(message):
    """Write message to log file and print to console"""
    print(message)
    with open(LOG_FILE, 'a') as log:
        log.write(message + "\n")

def main():
    """Main function to organize MCP and ontology related scripts"""
    log_message(f"Starting MCP and ontology scripts organization at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_message("="*80)
    
    # Make sure scripts directory exists
    if not os.path.exists("scripts"):
        log_message("Error: scripts directory does not exist. Aborting.")
        return False
    
    # Track what we've done
    moved_files = []
    skipped_files = []
    
    # Move files to scripts directory
    log_message("\n== Moving files to scripts directory ==")
    for file_name in MCP_ONTOLOGY_SCRIPTS:
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
    
    # Summarize what we did
    log_message("\n== Summary ==")
    log_message(f"Files moved to scripts directory: {len(moved_files)}")
    for file in moved_files:
        log_message(f"  - {file}")
    
    log_message(f"\nFiles skipped: {len(skipped_files)}")
    for file in skipped_files:
        log_message(f"  - {file}")
    
    log_message("\nNotes:")
    log_message("1. Files moved to the scripts directory are diagnostic and utility tools for MCP server and ontology management.")
    log_message("2. These scripts can be used for debugging, verification, and maintenance tasks.")
    log_message("3. A log of all actions has been saved to: " + LOG_FILE)
    
    return True

if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)
