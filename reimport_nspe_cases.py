#!/usr/bin/env python3
"""
Script to clean up incorrectly imported NSPE cases and reimport them properly.
This script:
1. Removes cases with "Pre Header Utility Links" title
2. Fetches and processes case content with improved extraction logic
3. Updates the engineering ethics ontology if needed
4. Creates RDF triples for the cases
5. Imports the cases to the Engineering world
"""

import os
import sys
import subprocess
import time
import argparse

def run_command(command, description):
    """
    Run a shell command and print the output.
    """
    print(f"\n===== {description} =====\n")
    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True
        )
        
        # Print output in real-time
        for line in process.stdout:
            print(line.strip())
        
        process.wait()
        
        if process.returncode == 0:
            print(f"\n✅ {description} completed successfully")
            return True
        else:
            print(f"\n❌ {description} failed with return code {process.returncode}")
            return False
    except Exception as e:
        print(f"\n❌ {description} failed with exception: {str(e)}")
        return False

def ensure_data_directories():
    """
    Ensure all required data directories exist.
    """
    directories = [
        "data",
        "data/case_triples"
    ]
    
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Created directory: {directory}")

def cleanup_incorrect_cases(world_id=1):
    """
    Clean up incorrectly imported cases with "Pre Header Utility Links" title.
    """
    return run_command(
        f"python cleanup_header_links_cases.py --world-id {world_id}",
        "Cleaning up incorrectly imported cases"
    )

def fetch_nspe_cases():
    """
    Fetch NSPE case content from URLs using the improved scraper.
    """
    return run_command(
        "python improved_fetch_nspe_cases.py --delay 1.5",
        "Fetching NSPE case content with improved extraction"
    )

def update_ontology():
    """
    Update the engineering ethics ontology with new concepts.
    """
    return run_command(
        "python update_engineering_ontology.py",
        "Updating engineering ethics ontology"
    )

def create_nspe_case_triples():
    """
    Create RDF triples for NSPE cases.
    """
    return run_command(
        "python create_nspe_ethics_cases.py --export-only",
        "Creating RDF triples for NSPE cases"
    )

def import_cases_to_world(world_id=1):
    """
    Import NSPE cases into the specified world.
    """
    return run_command(
        f"python import_nspe_cases_to_world.py --world-id {world_id} --skip-cleanup",
        f"Importing NSPE cases to world {world_id}"
    )

def list_imported_cases():
    """
    List all imported NSPE cases.
    """
    return run_command(
        "python list_nspe_world_cases.py",
        "Listing imported NSPE cases"
    )

def main():
    """
    Main function to clean up and reimport NSPE ethics cases.
    """
    parser = argparse.ArgumentParser(description='Clean up and reimport NSPE ethics cases')
    parser.add_argument('--world-id', type=int, default=1,
                        help='World ID to import cases into (default: 1)')
    parser.add_argument('--skip-cleanup', action='store_true',
                        help='Skip cleaning up incorrect cases')
    parser.add_argument('--skip-fetch', action='store_true',
                        help='Skip fetching cases from URLs')
    parser.add_argument('--skip-ontology', action='store_true',
                        help='Skip updating the ontology')
    parser.add_argument('--skip-triples', action='store_true',
                        help='Skip creating RDF triples')
    parser.add_argument('--skip-import', action='store_true',
                        help='Skip importing cases to world')
    args = parser.parse_args()
    
    print("===== NSPE Ethics Cases Reimport Process =====")
    print(f"Target world ID: {args.world_id}")
    
    # Create necessary directories
    ensure_data_directories()
    
    # Step 1: Clean up incorrect cases
    if not args.skip_cleanup:
        if not cleanup_incorrect_cases(args.world_id):
            print("\n❌ Failed to clean up incorrect cases. Stopping process.")
            return
    else:
        print("\n⏩ Skipping cleanup as requested")
    
    # Step 2: Fetch NSPE case content with improved extraction
    if not args.skip_fetch:
        if not fetch_nspe_cases():
            print("\n❌ Failed to fetch NSPE case content. Stopping process.")
            return
    else:
        print("\n⏩ Skipping case fetching as requested")
    
    # Step 3: Update ontology with new concepts
    if not args.skip_ontology:
        if not update_ontology():
            print("\n❌ Failed to update ontology. Stopping process.")
            return
    else:
        print("\n⏩ Skipping ontology update as requested")
    
    # Step 4: Create RDF triples for NSPE cases
    if not args.skip_triples:
        if not create_nspe_case_triples():
            print("\n❌ Failed to create RDF triples. Stopping process.")
            return
    else:
        print("\n⏩ Skipping triple creation as requested")
    
    # Step 5: Import cases to world
    if not args.skip_import:
        if not import_cases_to_world(args.world_id):
            print("\n❌ Failed to import cases to world. Stopping process.")
            return
    else:
        print("\n⏩ Skipping case import as requested")
    
    # Step 6: List imported cases
    list_imported_cases()
    
    print("\n✅ NSPE ethics cases reimport process completed successfully")
    print(f"Correctly formatted cases have been added to world ID {args.world_id}")
    print("You can view these cases in the Cases tab of the world")

if __name__ == "__main__":
    main()
