#!/usr/bin/env python
"""
Utility script to clean up guideline concepts and related data for testing.
This script executes the SQL cleanup script in a safe way and provides status feedback.
"""

import os
import subprocess
import sys
from datetime import datetime

def run_command(cmd):
    """Run a shell command and return output"""
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        shell=True,
        text=True
    )
    stdout, stderr = process.communicate()
    return process.returncode, stdout, stderr

def main():
    print("=" * 70)
    print("Running Guideline Concept Cleanup")
    print("=" * 70)
    
    # Get the script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Path to the SQL script (relative to this script)
    sql_script_path = os.path.join(script_dir, "sql", "cleanup_guideline_concepts.sql")
    
    # Check if the SQL script exists
    if not os.path.isfile(sql_script_path):
        print(f"Error: SQL script not found at {sql_script_path}")
        return 1
    
    print(f"Found SQL cleanup script: {sql_script_path}")
    
    # Check for Docker environment
    print("Checking Docker container for PostgreSQL...")
    
    # Detect environment and set PostgreSQL container name
    container_name = "proethica-postgres"
    if "CODESPACES" in os.environ and os.environ["CODESPACES"] == "true":
        print("Detected GitHub Codespaces environment")
    
    # Check if Docker is available
    returncode, stdout, stderr = run_command("docker --version")
    if returncode != 0:
        print("Error: Docker is not available")
        return 1
    
    print(f"Using Docker with container: {container_name}")
    
    # Check if PostgreSQL container is running
    returncode, stdout, stderr = run_command(f"docker ps -q -f name={container_name}")
    if not stdout.strip():
        print(f"Error: PostgreSQL container '{container_name}' is not running")
        return 1
    
    print(f"Container {container_name} is running")
    
    # First get the counts before cleanup for reporting
    print("\n" + "="*40)
    print("CURRENT DATABASE STATE:")
    print("="*40)
    
    count_query = """
    SELECT COUNT(*) FROM public.entity_triples WHERE entity_type = 'guideline_concept';
    SELECT COUNT(*) FROM public.guidelines;
    SELECT COUNT(*) FROM public.documents WHERE doc_metadata->>'guideline_id' IS NOT NULL;
    """
    
    returncode, stdout, stderr = run_command(
        f"docker exec {container_name} psql -U postgres -d ai_ethical_dm -c \"{count_query}\""
    )
    if returncode != 0:
        print(f"Error checking database state: {stderr}")
    else:
        print(stdout)
    
    # Confirm before proceeding
    confirmation = input("Do you want to proceed with cleanup? (y/n): ")
    if confirmation.lower() != 'y':
        print("Operation cancelled.")
        return 0
    
    # Execute the SQL cleanup script
    print("\n" + "="*40)
    print("EXECUTING CLEANUP SCRIPT...")
    print("="*40)
    
    returncode, stdout, stderr = run_command(
        f"docker exec -i {container_name} psql -U postgres -d ai_ethical_dm < {sql_script_path}"
    )
    
    if returncode != 0:
        print(f"Error executing SQL cleanup script: {stderr}")
        return 1
    
    print(stdout)
    print("SQL cleanup script executed successfully")
    
    # Verify the cleanup
    print("\n" + "="*40)
    print("VERIFICATION AFTER CLEANUP:")
    print("="*40)
    
    verification_query = """
    SELECT COUNT(*) AS "Remaining Guideline Concept Triples"
    FROM public.entity_triples
    WHERE entity_type = 'guideline_concept';
    
    SELECT COUNT(*) AS "Remaining Guidelines"
    FROM public.guidelines;
    
    SELECT COUNT(*) AS "Documents still having guideline references"
    FROM public.documents
    WHERE doc_metadata->>'guideline_id' IS NOT NULL;
    """
    
    returncode, stdout, stderr = run_command(
        f"docker exec {container_name} psql -U postgres -d ai_ethical_dm -c \"{verification_query}\""
    )
    if returncode != 0:
        print(f"Error verifying cleanup: {stderr}")
        return 1
    
    print(stdout)
    
    # Generate log file
    log_filename = f"cleanup_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    with open(log_filename, 'w') as log_file:
        log_file.write("Guideline Concept Cleanup Log\n")
        log_file.write("=" * 40 + "\n")
        log_file.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_file.write(f"SQL Script: {sql_script_path}\n")
        log_file.write(f"Container: {container_name}\n\n")
        log_file.write("Cleanup Output:\n")
        log_file.write(stdout)
    
    print(f"\nLog saved to: {log_filename}")
    
    print("\n" + "="*40)
    print("CLEANUP COMPLETE")
    print("="*40)
    print("You can now proceed with fresh guideline extraction testing.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
