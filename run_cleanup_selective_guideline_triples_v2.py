#!/usr/bin/env python3
"""
Selective Guideline Triple Cleanup Script (Version 2)

This script preserves only the guideline triples associated with
guideline ID 43 (which is linked to document ID 190 - Engineering Ethics).
It removes all other guideline triples to reduce processing time
when associating guidelines with document sections.
"""

import os
import sys
import datetime
import subprocess

SQL_SCRIPT_PATH = 'sql/cleanup_selective_guideline_triples_v2.sql'
LOG_DIR = '.'

def check_docker_container():
    """Check if the PostgreSQL Docker container is running."""
    print("Checking Docker container for PostgreSQL...")
    try:
        result = subprocess.run(
            ["docker", "ps", "--filter", "name=proethica-postgres", "--format", "{{.Names}}"],
            capture_output=True, text=True, check=True
        )
        container_name = result.stdout.strip()
        
        if not container_name:
            print("PostgreSQL container not found. Make sure the container is running.")
            return None
        
        print(f"Using Docker with container: {container_name}")
        
        # Check if container is running
        result = subprocess.run(
            ["docker", "container", "inspect", "-f", "{{.State.Running}}", container_name],
            capture_output=True, text=True, check=True
        )
        
        if result.stdout.strip() == "true":
            print(f"Container {container_name} is running\n")
            return container_name
        else:
            print(f"Container {container_name} exists but is not running. Please start it.")
            return None
            
    except subprocess.CalledProcessError as e:
        print(f"Error checking Docker container: {e}")
        return None

def execute_sql_script(container_name):
    """Execute the SQL cleanup script in the PostgreSQL Docker container."""
    if not os.path.exists(SQL_SCRIPT_PATH):
        print(f"SQL script not found at: {SQL_SCRIPT_PATH}")
        return False
    
    print("=" * 40)
    print("CURRENT DATABASE STATE:")
    print("=" * 40)
    
    # Show current guidelines
    subprocess.run([
        "docker", "exec", container_name, 
        "psql", "-U", "postgres", "-d", "ai_ethical_dm", 
        "-c", "SELECT id, title, world_id FROM guidelines"
    ])
    
    # Check total count of entity_triples with guideline_concept type
    subprocess.run([
        "docker", "exec", container_name, 
        "psql", "-U", "postgres", "-d", "ai_ethical_dm", 
        "-c", "SELECT COUNT(*) as total FROM entity_triples WHERE entity_type = 'guideline_concept'"
    ])
    
    # Ask for confirmation
    response = input("\nDo you want to proceed with selective cleanup? (y/n): ")
    if response.lower() != 'y':
        print("Operation cancelled.")
        return False
    
    print("\n" + "=" * 40)
    print("EXECUTING SELECTIVE CLEANUP SCRIPT...")
    print("=" * 40)
    
    # Execute the SQL script
    try:
        with open(SQL_SCRIPT_PATH, 'r') as f:
            sql_content = f.read()
            
        result = subprocess.run([
            "docker", "exec", container_name, 
            "psql", "-U", "postgres", "-d", "ai_ethical_dm", 
            "-c", sql_content
        ], capture_output=True, text=True, check=True)
        
        # Save the output to a log file
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        log_file = f"cleanup_log_{timestamp}.txt"
        log_path = os.path.join(LOG_DIR, log_file)
        
        with open(log_path, 'w') as f:
            f.write(result.stdout)
        
        print(result.stdout)
        print(f"\nSQL cleanup script executed successfully")
        print(f"\nLog saved to: {log_file}")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"Error executing SQL script: {e}")
        print(f"Error details: {e.stderr}")
        return False

def verify_cleanup(container_name):
    """Verify the cleanup operation was successful."""
    print("\n" + "=" * 40)
    print("VERIFICATION AFTER CLEANUP:")
    print("=" * 40)
    
    # Check that only triples for guideline 43 remain
    subprocess.run([
        "docker", "exec", container_name, 
        "psql", "-U", "postgres", "-d", "ai_ethical_dm", 
        "-c", "SELECT COUNT(*) as remaining FROM entity_triples WHERE entity_type = 'guideline_concept'"
    ])
    
    return True

def main():
    """Main function to run the cleanup script."""
    print("=" * 70)
    print("Running Selective Guideline Triple Cleanup (V2)")
    print("This will preserve only triples for guideline ID 43 (linked to document 190)")
    print("=" * 70)
    
    # Find SQL cleanup script
    if os.path.exists(SQL_SCRIPT_PATH):
        print(f"Found SQL cleanup script: {os.path.abspath(SQL_SCRIPT_PATH)}")
    else:
        print(f"SQL cleanup script not found at: {SQL_SCRIPT_PATH}")
        return 1
        
    # Check Docker container
    container_name = check_docker_container()
    if not container_name:
        return 1
    
    # Execute the SQL script
    if not execute_sql_script(container_name):
        return 1
    
    # Verify the cleanup
    if not verify_cleanup(container_name):
        return 1
    
    print("\n" + "=" * 40)
    print("CLEANUP COMPLETE")
    print("=" * 40)
    print("You should now have only the guideline triples associated with guideline ID 43")
    print("(linked to document ID 190 - Engineering Ethics)")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
