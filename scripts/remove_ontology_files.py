#!/usr/bin/env python3
"""
Script to remove ontology files while preserving directory structure.
This ensures the system will use the database versions of ontologies
instead of falling back to the file system.
"""

import os
import json
import shutil

def remove_ontology_files():
    """Remove ontology files while preserving directory structure."""
    base_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'ontologies')

    # Create empty metadata.json and versions.json files
    print("Creating empty metadata.json and versions.json files...")
    with open(os.path.join(base_dir, 'metadata.json'), 'w') as f:
        f.write('[]')

    with open(os.path.join(base_dir, 'versions.json'), 'w') as f:
        f.write('[]')

    # Process domains directory
    domains_dir = os.path.join(base_dir, 'domains')
    if os.path.exists(domains_dir) and os.path.isdir(domains_dir):
        print(f"Processing domains directory: {domains_dir}")

        # List domains
        domains = [d for d in os.listdir(domains_dir) if os.path.isdir(os.path.join(domains_dir, d))]
        print(f"Found {len(domains)} domain directories: {', '.join(domains)}")

        for domain in domains:
            domain_dir = os.path.join(domains_dir, domain)

            # Process main directory
            main_dir = os.path.join(domain_dir, 'main')
            if os.path.exists(main_dir) and os.path.isdir(main_dir):
                print(f"Processing {domain}/main directory...")

                # Handle current.ttl
                current_file = os.path.join(main_dir, 'current.ttl')
                if os.path.exists(current_file):
                    print(f"  Removing {current_file}")
                    os.remove(current_file)
                    # Create empty file
                    with open(current_file, 'w') as f:
                        f.write('# This file is intentionally empty - ontology now stored in database\n')

                # Process versions directory
                versions_dir = os.path.join(main_dir, 'versions')
                if os.path.exists(versions_dir) and os.path.isdir(versions_dir):
                    print(f"  Processing {domain}/main/versions directory...")

                    # List version files
                    version_files = [f for f in os.listdir(versions_dir) if f.endswith('.ttl')]
                    print(f"    Found {len(version_files)} version files: {', '.join(version_files)}")

                    for vfile in version_files:
                        vfile_path = os.path.join(versions_dir, vfile)
                        print(f"    Removing {vfile_path}")
                        os.remove(vfile_path)
                        # Create empty file
                        with open(vfile_path, 'w') as f:
                            f.write('# This file is intentionally empty - version now stored in database\n')
    
    # Also process MCP ontology directory
    mcp_ontology_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mcp', 'ontology')
    if os.path.exists(mcp_ontology_dir) and os.path.isdir(mcp_ontology_dir):
        print(f"\nProcessing MCP ontology directory: {mcp_ontology_dir}")
        
        # Find TTL files
        ttl_files = [f for f in os.listdir(mcp_ontology_dir) if f.endswith('.ttl')]
        print(f"Found {len(ttl_files)} TTL files: {', '.join(ttl_files)}")
        
        for ttl_file in ttl_files:
            file_path = os.path.join(mcp_ontology_dir, ttl_file)
            print(f"  Removing {file_path}")
            os.remove(file_path)
            # Create empty placeholder
            with open(file_path, 'w') as f:
                f.write(f'# This file is intentionally empty - ontology now stored in database\n')
                f.write(f'# Original file was archived before removal\n')

    print("\nDone! All ontology files have been replaced with empty placeholder files.")
    print("The system will now use ontologies from the database.")

if __name__ == "__main__":
    remove_ontology_files()
