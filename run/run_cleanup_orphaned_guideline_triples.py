#!/usr/bin/env python3
"""
Script to clean up orphaned guideline triples from the database.
This removes triples associated with guidelines that no longer exist.
"""

import subprocess
import sys
import os
from datetime import datetime

def check_docker_container():
    """Check if the PostgreSQL Docker container is running."""
    result = subprocess.run(['docker', 'ps', '--filter', 'name=proethica-postgres', '--format', '{{.Names}}'], 
                          capture_output=True, text=True)
    return 'proethica-postgres' in result.stdout

def run_cleanup():
    """Execute the cleanup SQL script."""
    print("=" * 80)
    print("ORPHANED GUIDELINE TRIPLES CLEANUP")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check if Docker container is running
    if not check_docker_container():
        print("ERROR: PostgreSQL Docker container 'proethica-postgres' is not running.")
        print("Please start the container with: docker-compose up -d postgres")
        return 1
    
    print("This script will remove guideline triples that are associated with:")
    print("1. Guidelines that no longer exist in the database")
    print("2. Documents that have been deleted")
    print("3. Invalid guideline references in metadata")
    print()
    print("This includes triples referencing guideline IDs that don't have")
    print("corresponding entries in the guidelines table (e.g., Guideline 46).")
    print()
    
    # Get user confirmation
    response = input("Do you want to proceed? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Cleanup cancelled.")
        return 0
    
    print("\nExecuting cleanup script...")
    print("-" * 80)
    
    # Build the docker exec command
    sql_file = '/home/chris/proethica/sql/cleanup_orphaned_guideline_triples.sql'
    cmd = [
        'docker', 'exec', '-i', 'proethica-postgres',
        'psql', '-U', 'postgres', '-d', 'ai_ethical_dm', '-f', '-'
    ]
    
    try:
        # Read the SQL file
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        
        # Execute the SQL
        result = subprocess.run(cmd, input=sql_content, capture_output=True, text=True)
        
        # Print output
        if result.stdout:
            print(result.stdout)
        
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode != 0:
            print(f"\nERROR: Command failed with return code {result.returncode}")
            return result.returncode
            
        print("-" * 80)
        print("\nCleanup completed successfully!")
        print()
        print("Summary:")
        print("- Orphaned guideline triples have been removed")
        print("- Document metadata has been cleaned")
        print("- Database integrity has been restored")
        print()
        print("You can verify the results by checking:")
        print("1. The manage_triples page for any guideline")
        print("2. The cleanup summary output above")
        
        # Generate log file
        log_file = f"cleanup_orphaned_guideline_triples_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        with open(log_file, 'w') as f:
            f.write(f"Cleanup executed at: {datetime.now()}\n")
            f.write(f"Output:\n{result.stdout}\n")
            if result.stderr:
                f.write(f"Errors:\n{result.stderr}\n")
        
        print(f"\nLog saved to: {log_file}")
        
        return 0
        
    except FileNotFoundError:
        print(f"ERROR: SQL file not found: {sql_file}")
        return 1
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(run_cleanup())