#!/usr/bin/env python3
"""
Script to archive ontology TTL files from the mcp/ontology directory.
This creates a backup of the TTL files before they are replaced with placeholders,
ensuring we have original copies in case they are needed later.
"""

import os
import sys
import shutil
import datetime
import argparse

def archive_ontology_files(archive_dir=None, backup_readme=True):
    """
    Archive TTL files from the mcp/ontology directory to a backup location.
    
    Args:
        archive_dir (str): Directory to archive files to. If None, creates a timestamped dir.
        backup_readme (bool): Whether to include README and guide files in the backup.
    
    Returns:
        str: Path to the archive directory
    """
    # Get base directories
    base_dir = os.path.dirname(os.path.dirname(__file__))
    ontology_dir = os.path.join(base_dir, 'mcp', 'ontology')
    
    # Create archive directory if not specified
    if not archive_dir:
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_dir = os.path.join(base_dir, f'ontologies_archive_{timestamp}')
    
    # Create the directory if it doesn't exist
    if not os.path.exists(archive_dir):
        os.makedirs(archive_dir)
        print(f"Created archive directory: {archive_dir}")
    
    # Get list of TTL files
    ttl_files = [f for f in os.listdir(ontology_dir) if f.endswith('.ttl')]
    print(f"Found {len(ttl_files)} TTL files to archive")
    
    # Archive each TTL file
    for ttl_file in ttl_files:
        source_path = os.path.join(ontology_dir, ttl_file)
        dest_path = os.path.join(archive_dir, ttl_file)
        
        shutil.copy2(source_path, dest_path)
        print(f"Archived {ttl_file}")
    
    # Check if we should back up README and guide files
    if backup_readme:
        readme_files = [
            f for f in os.listdir(ontology_dir) 
            if f.endswith('.md') or os.path.isdir(os.path.join(ontology_dir, f))
        ]
        
        for readme_file in readme_files:
            source_path = os.path.join(ontology_dir, readme_file)
            dest_path = os.path.join(archive_dir, readme_file)
            
            if os.path.isdir(source_path):
                # For directories (like 'archive'), copy recursively
                if os.path.exists(dest_path):
                    shutil.rmtree(dest_path)
                shutil.copytree(source_path, dest_path)
                print(f"Archived directory {readme_file}")
            else:
                # For individual files
                shutil.copy2(source_path, dest_path)
                print(f"Archived {readme_file}")
    
    # Create a README in the archive directory
    with open(os.path.join(archive_dir, 'ARCHIVE_README.md'), 'w') as f:
        f.write(f"""# Ontology TTL File Archive

This directory contains archived copies of the original TTL ontology files that were previously 
stored in the `mcp/ontology` directory. These files have been archived as part of the migration
to database-based ontology storage.

**Archive created on:** {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Files Included

The following TTL files are included in this archive:

```
{os.linesep.join(ttl_files)}
```

## Usage

These files are kept for reference purposes only. The active system now uses 
ontologies stored directly in the database. If you need to restore these files,
copy them back to the `mcp/ontology` directory, but note that this may cause
conflicts if the database versions have been modified.
""")
    
    print(f"\nArchive complete. {len(ttl_files)} TTL files archived to {archive_dir}")
    print(f"Archive README created at {os.path.join(archive_dir, 'ARCHIVE_README.md')}")
    
    return archive_dir

def main():
    """Run the archive function with command-line arguments."""
    parser = argparse.ArgumentParser(description='Archive ontology TTL files.')
    parser.add_argument('--dir', type=str, help='Custom directory to archive files to')
    parser.add_argument('--no-readme', action='store_true', help='Do not archive README and guide files')
    
    args = parser.parse_args()
    
    try:
        archive_dir = archive_ontology_files(
            archive_dir=args.dir,
            backup_readme=not args.no_readme
        )
        
        print("\nNext steps:")
        print("1. Run update_ontology_mcp_server.py to modify the MCP server to load ontologies from the database")
        print("2. Run remove_ontology_files.py to replace TTL files with placeholders")
        print("3. Restart the MCP server to apply changes")
        
        return 0
    except Exception as e:
        print(f"ERROR: Failed to archive ontology files: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
