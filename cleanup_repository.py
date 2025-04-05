#!/usr/bin/env python3
"""
Script to clean up the repository by deleting files that are no longer needed.
This script will create a log file of all deletions for reference.
"""

import os
import datetime
import sys

# Files to delete
FILES_TO_DELETE = [
    # NSPE Case Integration Scripts
    "cleanup_nspe_scenarios.py",
    "cleanup_nspe_scenarios_auto.py",
    "check_worlds_and_scenarios.py",
    "check_world_cases.py",
    "check_world_ontology.py", 
    "list_nspe_ethics_cases.py",
    
    # Obsolete Root Directory Scripts
    "archive_obsolete_db_scripts.py",
    "add_characters_to_scenario1.py",
    "add_resources_conditions_to_scenario1.py",
    "populate_scenario_template.py",
    
    # Testing and Setup Scripts
    "scripts/test_document.txt",
    "scripts/implement_phase1.sh",
    "scripts/implement_phase1_fixed.py",
    
    # Older Backups
    "backups/ai_ethical_dm_backup_20250323_135340.dump",
    "backups/ai_ethical_dm_backup_20250326_110159.dump"
]

def cleanup_repository():
    """
    Delete files that are no longer needed and log the deletions.
    """
    # Create log file
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"cleanup_log_{timestamp}.txt"
    
    # Results tracking
    deleted_files = []
    failed_files = []
    skipped_files = []
    
    # Write initial log entry
    with open(log_filename, 'w') as log_file:
        log_file.write(f"Repository Cleanup Log - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_file.write("=" * 70 + "\n\n")
        log_file.write(f"Files scheduled for deletion: {len(FILES_TO_DELETE)}\n\n")
    
    # Process each file
    for file_path in FILES_TO_DELETE:
        try:
            # Confirm file exists
            if not os.path.exists(file_path):
                message = f"SKIPPED: {file_path} - File does not exist"
                skipped_files.append(file_path)
                print(message)
                with open(log_filename, 'a') as log_file:
                    log_file.write(f"{message}\n")
                continue
                
            # Delete the file
            os.remove(file_path)
            
            # Check if deletion was successful
            if not os.path.exists(file_path):
                message = f"DELETED: {file_path}"
                deleted_files.append(file_path)
            else:
                message = f"FAILED: {file_path} - File still exists after deletion attempt"
                failed_files.append(file_path)
                
            # Log the result
            print(message)
            with open(log_filename, 'a') as log_file:
                log_file.write(f"{message}\n")
                
        except Exception as e:
            message = f"ERROR: {file_path} - {str(e)}"
            failed_files.append(file_path)
            print(message)
            with open(log_filename, 'a') as log_file:
                log_file.write(f"{message}\n")
    
    # Write summary to log
    with open(log_filename, 'a') as log_file:
        log_file.write("\n" + "=" * 70 + "\n")
        log_file.write(f"SUMMARY - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_file.write(f"Total files processed: {len(FILES_TO_DELETE)}\n")
        log_file.write(f"Successfully deleted: {len(deleted_files)}\n")
        log_file.write(f"Failed to delete: {len(failed_files)}\n")
        log_file.write(f"Skipped (not found): {len(skipped_files)}\n")
    
    # Return the results
    print("\n" + "=" * 70)
    print(f"Cleanup completed. See {log_filename} for details.")
    print(f"Successfully deleted: {len(deleted_files)} files")
    print(f"Failed to delete: {len(failed_files)} files")
    print(f"Skipped (not found): {len(skipped_files)} files")
    
    return deleted_files, failed_files, skipped_files

if __name__ == "__main__":
    print("Starting repository cleanup...")
    cleanup_repository()
