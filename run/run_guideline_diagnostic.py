#!/usr/bin/env python3
"""
Script to diagnose guideline triple issues.
This helps understand why "Other Guidelines" appear when there's only one guideline.
"""

import subprocess
import sys
import os

def run_diagnostic():
    """Execute the diagnostic SQL script."""
    print("=" * 80)
    print("GUIDELINE TRIPLE DIAGNOSTIC")
    print("=" * 80)
    print()
    
    # Build the docker exec command
    sql_file = '/home/chris/proethica/sql/diagnose_guideline_triples.sql'
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
        
        return result.returncode
        
    except FileNotFoundError:
        print(f"ERROR: SQL file not found: {sql_file}")
        return 1
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(run_diagnostic())