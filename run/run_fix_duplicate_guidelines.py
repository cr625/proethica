#!/usr/bin/env python3
"""
Script to fix duplicate guidelines pointing to the same document.
This consolidates multiple guideline records into one per document.
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

def run_fix():
    """Execute the fix duplicate guidelines SQL script."""
    print("=" * 80)
    print("FIX DUPLICATE GUIDELINES")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check if Docker container is running
    if not check_docker_container():
        print("ERROR: PostgreSQL Docker container 'proethica-postgres' is not running.")
        print("Please start the container with: docker-compose up -d postgres")
        return 1
    
    print("This script will fix the issue of multiple guideline records")
    print("pointing to the same document by:")
    print()
    print("1. Keeping the newest guideline record for each document")
    print("2. Updating all triples to point to the kept guideline")
    print("3. Updating document metadata to reference the kept guideline")
    print("4. Deleting the old duplicate guideline records")
    print()
    print("This will ensure a 1:1 relationship between documents and guidelines.")
    print()
    
    # Get user confirmation
    response = input("Do you want to proceed? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Fix cancelled.")
        return 0
    
    print("\nExecuting fix script...")
    print("-" * 80)
    
    # Build the docker exec command
    sql_file = '/home/chris/proethica/sql/fix_duplicate_guidelines.sql'
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
        print("\nFix completed successfully!")
        print()
        print("Results:")
        print("- Duplicate guidelines have been consolidated")
        print("- Each document now has only one associated guideline")
        print("- All triples have been updated to reference the correct guideline")
        print("- The 'Other Guidelines' issue should now be resolved")
        print()
        print("You can verify by:")
        print("1. Checking the manage_triples page - 'Other Guidelines' count should be 0")
        print("2. Running the diagnostic script to confirm the fix")
        
        # Generate log file
        log_file = f"fix_duplicate_guidelines_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        with open(log_file, 'w') as f:
            f.write(f"Fix executed at: {datetime.now()}\n")
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
    sys.exit(run_fix())