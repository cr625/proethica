#!/usr/bin/env python3
"""
Script to remove duplicate triples from guideline 46.
This keeps only the oldest triple for each unique (subject, predicate, object) combination.
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

def run_deduplication():
    """Execute the duplicate removal SQL script."""
    print("=" * 80)
    print("REMOVE DUPLICATE TRIPLES FROM GUIDELINE 46")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check if Docker container is running
    if not check_docker_container():
        print("ERROR: PostgreSQL Docker container 'proethica-postgres' is not running.")
        print("Please start the container with: docker-compose up -d postgres")
        return 1
    
    print("This script will remove duplicate triples from guideline 46 by:")
    print("1. Identifying groups of identical triples (same subject, predicate, object)")
    print("2. Keeping only the oldest triple (lowest ID) from each group")
    print("3. Deleting all other duplicates")
    print()
    print("Analysis shows approximately 177 duplicate triples out of 443 total.")
    print("After deduplication, you should have ~266 unique triples.")
    print()
    
    # Get user confirmation
    response = input("Do you want to proceed with deduplication? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Deduplication cancelled.")
        return 0
    
    print("\nExecuting deduplication script...")
    print("-" * 80)
    
    # Build the docker exec command
    sql_file = '/home/chris/proethica/sql/remove_duplicate_triples.sql'
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
        
        if result.stderr and "NOTICE" not in result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode != 0:
            print(f"\nERROR: Command failed with return code {result.returncode}")
            return result.returncode
            
        print("-" * 80)
        print("\nDeduplication completed successfully!")
        print()
        print("Results:")
        print("- Duplicate triples have been removed")
        print("- Only unique triples remain in guideline 46")
        print("- The manage_triples page should now show clean data")
        print()
        print("Next steps:")
        print("1. Check the manage_triples page to verify the cleanup")
        print("2. The deduplication service will prevent future duplicates during normal operations")
        
        # Generate log file
        log_file = f"remove_duplicate_triples_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        with open(log_file, 'w') as f:
            f.write(f"Deduplication executed at: {datetime.now()}\n")
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
    sys.exit(run_deduplication())