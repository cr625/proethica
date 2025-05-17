#!/usr/bin/env python3
"""
Script to execute the cleanup_guideline_concepts.sql script to remove all
guideline concepts, triples, and reset document metadata for testing.
"""

import os
import sys
import subprocess
import tempfile
import time

# Database connection parameters for Docker container
CONTAINER_NAME = "proethica-postgres"
DB_NAME = "ai_ethical_dm"
DB_USER = "postgres"
DB_PASS = "PASS"

def check_container_running():
    """Check if the database container is running."""
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", f"name={CONTAINER_NAME}", "--format", "{{.Names}}"],
            capture_output=True, text=True, check=True
        )
        return CONTAINER_NAME in result.stdout
    except subprocess.CalledProcessError:
        return False

def execute_sql_in_container(sql_file):
    """Execute an SQL file inside the PostgreSQL container."""
    # Check if container is running
    if not check_container_running():
        print(f"Error: Container '{CONTAINER_NAME}' is not running!")
        print("Please ensure the database container is running before proceeding.")
        sys.exit(1)
    
    # Read the SQL file
    with open(sql_file, 'r') as f:
        sql_content = f.read()
    
    # Split the SQL into statements and filter out comments and empty lines
    raw_statements = sql_content.split(';')
    statements = []
    
    for stmt in raw_statements:
        # Remove comments and empty lines
        cleaned_stmt = []
        for line in stmt.split('\n'):
            line = line.strip()
            if line and not line.startswith('--'):
                cleaned_stmt.append(line)
        
        if cleaned_stmt:
            statements.append(' '.join(cleaned_stmt))
    
    # Track success
    success_count = 0
    failure_count = 0
    
    try:
        print(f"Executing SQL statements in container {CONTAINER_NAME}...")
        
        # First, display what would be deleted (SELECTs)
        print("\n--- Current Data Status ---")
        for query in [
            "SELECT COUNT(*) AS \"Guideline Concept Triples\" FROM public.entity_triples WHERE entity_type = 'guideline_concept'",
            "SELECT COUNT(*) AS \"Guidelines\" FROM public.guidelines",
            "SELECT COUNT(*) AS \"Documents with guideline references\" FROM public.documents WHERE doc_metadata->>'guideline_id' IS NOT NULL"
        ]:
            cmd = [
                "docker", "exec", "-u", "postgres", CONTAINER_NAME,
                "psql", "-d", DB_NAME, "-U", DB_USER, 
                "-c", query, "-t"  # -t for tuple only output (cleaner)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"{query}: {result.stdout.strip()}")
            else:
                print(f"Error getting data for {query}: {result.stderr.strip()}")
        
        # Execute the actual DELETE and UPDATE statements
        print("\n--- Executing Cleanup Statements ---")
        
        # 1. Delete all entity_triples for guideline concepts
        print("\n1. Deleting entity triples for guideline concepts...")
        delete_triples_cmd = [
            "docker", "exec", "-u", "postgres", CONTAINER_NAME,
            "psql", "-d", DB_NAME, "-U", DB_USER, 
            "-c", "DELETE FROM public.entity_triples WHERE entity_type = 'guideline_concept'",
            "-t"
        ]
        result = subprocess.run(delete_triples_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Success: {result.stdout.strip()}")
            success_count += 1
        else:
            print(f"Error: {result.stderr.strip()}")
            failure_count += 1
        
        # 2. Update document metadata to remove guideline references
        print("\n2. Updating document metadata to remove guideline_id references...")
        for field in ['guideline_id', 'analyzed', 'concepts_extracted', 
                     'concepts_selected', 'triples_created', 'analysis_date']:
            update_cmd = [
                "docker", "exec", "-u", "postgres", CONTAINER_NAME,
                "psql", "-d", DB_NAME, "-U", DB_USER, 
                "-c", f"UPDATE public.documents SET doc_metadata = doc_metadata - '{field}' WHERE doc_metadata->>'{field}' IS NOT NULL",
                "-t"
            ]
            result = subprocess.run(update_cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"Removed {field}: {result.stdout.strip()}")
                success_count += 1
            else:
                print(f"Error removing {field}: {result.stderr.strip()}")
                failure_count += 1
        
        # 3. Delete all guidelines
        print("\n3. Deleting all guidelines...")
        delete_guidelines_cmd = [
            "docker", "exec", "-u", "postgres", CONTAINER_NAME,
            "psql", "-d", DB_NAME, "-U", DB_USER, 
            "-c", "DELETE FROM public.guidelines",
            "-t"
        ]
        result = subprocess.run(delete_guidelines_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Success: {result.stdout.strip()}")
            success_count += 1
        else:
            print(f"Error: {result.stderr.strip()}")
            failure_count += 1
        
        # Verify the deletions
        print("\n--- Verification After Cleanup ---")
        for query in [
            "SELECT COUNT(*) AS \"Remaining Guideline Concept Triples\" FROM public.entity_triples WHERE entity_type = 'guideline_concept'",
            "SELECT COUNT(*) AS \"Remaining Guidelines\" FROM public.guidelines",
            "SELECT COUNT(*) AS \"Documents still having guideline references\" FROM public.documents WHERE doc_metadata->>'guideline_id' IS NOT NULL"
        ]:
            cmd = [
                "docker", "exec", "-u", "postgres", CONTAINER_NAME,
                "psql", "-d", DB_NAME, "-U", DB_USER, 
                "-c", query, "-t"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"{query}: {result.stdout.strip()}")
            else:
                print(f"Error getting data for {query}: {result.stderr.strip()}")
        
        # Report success
        print(f"\n--- SQL Execution Summary ---")
        print(f"Successful statements: {success_count}")
        print(f"Failed statements: {failure_count}")
        
        return failure_count == 0
    
    except Exception as e:
        print(f"Error executing SQL: {e}")
        return False

def main():
    """Main function to run the cleanup script."""
    print("Starting guideline concepts cleanup...")
    
    # Ask for confirmation
    response = input("This will delete all guideline concepts and reset document metadata. Continue? (y/n): ")
    if response.lower() != 'y':
        print("Operation cancelled.")
        return
    
    # Execute the SQL file
    sql_file = 'sql/cleanup_guideline_concepts.sql'
    success = execute_sql_in_container(sql_file)
    
    if success:
        print("\nCleanup complete!")
    else:
        print("\nCleanup failed. Please check the error messages above.")

if __name__ == "__main__":
    main()
