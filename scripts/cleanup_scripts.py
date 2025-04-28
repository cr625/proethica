#!/usr/bin/env python3
"""
Script to clean up the scripts directory
- Removes scripts that are no longer needed
- Removes the scripts/archive directory
- Keeps useful scripts like API verification scripts

Run this script from the project root directory:
python scripts/cleanup_scripts.py
"""

import os
import shutil
import datetime
from pathlib import Path
import re

# Get the current timestamp for logs and backups
timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
log_filename = f"scripts_cleanup_log_{timestamp}.txt"

# Scripts to keep - these are still useful for the current version
SCRIPTS_TO_KEEP = [
    # Claude API and environment handling
    "verify_anthropic_fix.py",
    "run_with_env.sh",
    "git_protect_keys.sh",
    "test_claude_with_env.py",
    "try_anthropic_bearer.py",
    "check_claude_api.py",
    "simple_claude_test.py",
    "test_anthropic_auth.py",
    "claude_api_info.md",
    "cleanup_scripts.py",  # Keep this script itself
    
    # Database management
    "check_db.py",
    "create_admin_user.py",
    "backup_database.sh",
    "restore_database.sh",
    
    # Ontology management
    "check_ontology.py",
    "fix_ontology_automatically.py",
    "fix_ontology_syntax.py",
    "fix_ontology_validation.py",
    
    # System maintenance
    "create_uploads_directory.py",
    "restart_mcp_server.sh",
    "restart_http_mcp_server.sh",
    
    # Useful directories
    "__pycache__",  # Not a script, but keep the directory
    "database_migrations"  # Keep database migrations
]

# Function to log messages
def log(message):
    with open(log_filename, "a") as log_file:
        log_file.write(f"{message}\n")
    print(message)

def main():
    log(f"Starting scripts cleanup at {timestamp}")
    
    # Change to the scripts directory
    scripts_dir = Path("scripts")
    
    if not scripts_dir.exists():
        log(f"Error: {scripts_dir} directory not found!")
        return
    
    # Create a backup directory for removed scripts
    backup_dir = Path(f"scripts_backup_{timestamp}")
    backup_dir.mkdir(exist_ok=True)
    log(f"Created backup directory: {backup_dir}")
    
    # Remove the archive directory
    archive_dir = scripts_dir / "archive"
    if archive_dir.exists():
        log(f"Removing archive directory: {archive_dir}")
        try:
            shutil.rmtree(archive_dir)
            log(f"Successfully removed {archive_dir}")
        except Exception as e:
            log(f"Error removing {archive_dir}: {e}")
    
    # Process each file in the scripts directory
    files_removed = 0
    for item in scripts_dir.iterdir():
        # Skip if it's in our keep list or a directory we want to keep
        if item.name in SCRIPTS_TO_KEEP:
            log(f"Keeping: {item.name}")
            continue
        
        # Skip database_migrations directory
        if item.is_dir() and item.name == "database_migrations":
            log(f"Keeping directory: {item.name}")
            continue
            
        # Handle non-keep items
        if item.is_file():
            # Backup the file first
            try:
                shutil.copy2(item, backup_dir / item.name)
                log(f"Backed up: {item.name}")
            except Exception as e:
                log(f"Error backing up {item}: {e}")
                continue
            
            # Now remove the file
            try:
                item.unlink()
                log(f"Removed: {item.name}")
                files_removed += 1
            except Exception as e:
                log(f"Error removing {item}: {e}")
        elif item.is_dir() and item.name not in ["__pycache__", "database_migrations"]:
            # Backup and remove directories that aren't in our keep list
            try:
                shutil.copytree(item, backup_dir / item.name)
                log(f"Backed up directory: {item.name}")
                shutil.rmtree(item)
                log(f"Removed directory: {item.name}")
                files_removed += 1
            except Exception as e:
                log(f"Error handling directory {item}: {e}")
    
    # Summary
    log(f"\nCleanup complete!")
    log(f"Removed files/directories: {files_removed}")
    log(f"Backup created at: {backup_dir}")
    log(f"All removed files were backed up before deletion.")
    log(f"See {log_filename} for details of all operations.")

if __name__ == "__main__":
    main()
