#!/usr/bin/env python3
"""
Script to identify and archive database scripts that are no longer applicable
due to the transition to the RDF triple-based data structure.
"""

import os
import shutil
import datetime

# Define the directory structure
SCRIPTS_DIR = "scripts"
ARCHIVE_DIR = os.path.join(SCRIPTS_DIR, "archive", "pre_rdf_migration")

# Create list of scripts that are obsolete due to RDF triple-based data structure
OBSOLETE_SCRIPTS = [
    # Old migration scripts related to pre-RDF structure
    "migrate_decisions_to_actions.py",
    "migrate_guidelines_to_documents.py",
    "run_guidelines_migration.py",
    "run_guidelines_migration.sh",
    "remove_guidelines_fields.py",
    "run_migration.py",
    
    # Character handling before RDF triples
    "fix_character_attributes.py",
    "fix_character_delete.py",
    "verify_character_role.py",
    
    # Old document/guideline handling
    "add_document_status_fields.py",
    "add_document_progress_fields.py",
    "create_document_tables.py",
    "manual_create_document_tables.py",
    "fix_document_status.py",
    
    # Decision/event handling replaced by RDF structures
    "create_simulation_sessions_table.py", 
    "create_simulation_states_table.py",
    "fix_action_parameters.py",
    "fix_event_parameters.py",
    "fix_llm_evaluation.py",
    "fix_sim_state.py",
    "update_decision_options.py",
    "update_all_decision_options.py", 
    "update_event_action_ids.py",
    "fix_scenario6_decision.py",
    "fix_scenario6_timeline.py",
    "check_decision_options.py",
    "check_events.py",
    "list_decision_actions.py",
    
    # Old database scripts without RDF support
    "drop_and_recreate_db.sh",
    "recreate_clean_db.py", 
    "clean_database.py",
    "clean_database_sql.py",
    "direct_recreate_db.sql",
    
    # Superseded by RDF-capable scripts
    "check_roles.py",
    "check_tables.py",
]

def archive_scripts():
    """Archive obsolete scripts to the pre_rdf_migration directory."""
    # Create archive directory if it doesn't exist
    if not os.path.exists(ARCHIVE_DIR):
        os.makedirs(ARCHIVE_DIR)
        print(f"Created archive directory: {ARCHIVE_DIR}")
    
    # Create a README file in the archive directory
    readme_path = os.path.join(ARCHIVE_DIR, "README.md")
    with open(readme_path, 'w') as f:
        f.write(f"""# Pre-RDF Migration Scripts Archive

This directory contains database scripts that became obsolete after the transition 
to the RDF triple-based data structure implemented in April 2025.

These scripts are preserved for historical reference but should not be used
with the current database structure.

Archived on: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Archive Contents

""")
        for script in OBSOLETE_SCRIPTS:
            f.write(f"- `{script}`\n")
    
    # Move each obsolete script to the archive directory
    moved_scripts = []
    missing_scripts = []
    
    for script in OBSOLETE_SCRIPTS:
        script_path = os.path.join(SCRIPTS_DIR, script)
        if os.path.exists(script_path):
            # Create backup with timestamp
            archive_path = os.path.join(ARCHIVE_DIR, script)
            shutil.copy2(script_path, archive_path)
            moved_scripts.append(script)
            print(f"Archived: {script}")
        else:
            missing_scripts.append(script)
    
    # Print summary
    print(f"\nArchive operation complete. Archived {len(moved_scripts)} scripts.")
    if missing_scripts:
        print(f"Note: The following {len(missing_scripts)} scripts were not found:")
        for script in missing_scripts:
            print(f"  - {script}")
    
    return moved_scripts, missing_scripts

def main():
    """Main function to run the script archiving process."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Archive obsolete database scripts.')
    parser.add_argument('--delete', action='store_true', help='Delete original scripts after archiving')
    parser.add_argument('--auto', action='store_true', help='Run without confirmation prompts')
    args = parser.parse_args()
    
    print("=== Archiving Obsolete Database Scripts ===\n")
    print(f"Scripts will be archived to: {ARCHIVE_DIR}")
    
    # Check if confirmation is needed
    if not args.auto:
        response = input("\nDo you want to proceed with archiving obsolete scripts? (y/N): ")
        if response.lower() != 'y':
            print("Operation cancelled.")
            return
    
    # Archive the scripts
    moved_scripts, missing_scripts = archive_scripts()
    
    # Check if original scripts should be deleted
    if moved_scripts and args.delete:
        print("\nDeleting original script files...")
        for script in moved_scripts:
            script_path = os.path.join(SCRIPTS_DIR, script)
            os.remove(script_path)
            print(f"Deleted original: {script}")
        print("\nDeletion operation complete.")
    elif moved_scripts and not args.auto:
        # Ask if user wants to delete the original scripts
        response = input("\nDo you want to delete the original script files? (y/N): ")
        if response.lower() == 'y':
            for script in moved_scripts:
                script_path = os.path.join(SCRIPTS_DIR, script)
                os.remove(script_path)
                print(f"Deleted original: {script}")
            print("\nDeletion operation complete.")
        else:
            print("\nOriginal scripts preserved.")
    else:
        print("\nOriginal scripts preserved.")
    
    print("\nArchive process completed.")

if __name__ == "__main__":
    main()
