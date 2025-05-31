#!/usr/bin/env python3
"""
Script for fresh start: Delete all guideline data and prepare for re-extraction.
This removes all guidelines and their triples so you can start clean.
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

def run_fresh_start():
    """Execute the fresh start SQL script."""
    print("=" * 80)
    print("FRESH START: DELETE ALL GUIDELINE DATA")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Check if Docker container is running
    if not check_docker_container():
        print("ERROR: PostgreSQL Docker container 'proethica-postgres' is not running.")
        print("Please start the container with: docker-compose up -d postgres")
        return 1
    
    print("⚠️  WARNING: This script will COMPLETELY DELETE all guideline data!")
    print()
    print("This will remove:")
    print("1. ALL guideline records from the guidelines table")
    print("2. ALL guideline concept triples from entity_triples")
    print("3. All guideline_id references from document metadata")
    print()
    print("After this cleanup, you will need to:")
    print("1. Go to the guidelines management page")
    print("2. Re-run concept extraction on your guideline document(s)")
    print("3. The deduplication service will ensure no duplicates are created")
    print()
    print("✅ Benefits of fresh start:")
    print("- Guaranteed clean data with no duplicates")
    print("- Uses the proper deduplication service during extraction")
    print("- Faster than cleaning up existing duplicates")
    print()
    
    # Double confirmation for destructive operation
    print("🔥 This is a DESTRUCTIVE operation that cannot be undone!")
    response1 = input("Are you sure you want to delete ALL guideline data? (yes/no): ").strip().lower()
    if response1 != 'yes':
        print("Fresh start cancelled.")
        return 0
        
    response2 = input("This will delete everything. Type 'DELETE ALL' to confirm: ").strip()
    if response2 != 'DELETE ALL':
        print("Fresh start cancelled.")
        return 0
    
    print("\nExecuting fresh start cleanup...")
    print("-" * 80)
    
    # Build the docker exec command
    sql_file = '/home/chris/proethica/sql/fresh_start_guideline.sql'
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
        print("\n✅ Fresh start completed successfully!")
        print()
        print("Results:")
        print("- All guideline data has been deleted")
        print("- Database is clean and ready for re-extraction")
        print("- No duplicates or orphaned data remain")
        print()
        print("🚀 Next steps:")
        print("1. Go to: http://localhost:3333/worlds/1/guidelines")
        print("2. Find your guideline document (should still exist)")
        print("3. Click 'Extract Concepts' or 'Manage Triples'")
        print("4. The deduplication service will ensure clean data")
        print()
        print("The fresh extraction will be much cleaner and faster than")
        print("the previous runs since there are no duplicates to check against.")
        
        # Generate log file
        log_file = f"fresh_start_guideline_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        with open(log_file, 'w') as f:
            f.write(f"Fresh start executed at: {datetime.now()}\n")
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
    sys.exit(run_fresh_start())