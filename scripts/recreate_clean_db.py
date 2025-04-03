#!/usr/bin/env python
"""
Script to recreate a clean database by:
1. Creating a backup of the current database
2. Dropping all tables
3. Recreating the schema with alembic
4. Initializing essential database data
"""

import os
import sys
import subprocess
import argparse
import time
from datetime import datetime

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def create_backup(backup_name=None):
    """Create a database backup."""
    if not backup_name:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"backup_before_clean_{timestamp}"
    
    print(f"\n=== Creating Database Backup: {backup_name} ===")
    
    backup_file = f"backups/{backup_name}.dump"
    
    try:
        # Run the backup script
        result = subprocess.run(
            ['bash', 'backups/backup_database.sh', backup_name],
            capture_output=True, text=True, check=True
        )
        print(result.stdout)
        return True, backup_file
    except subprocess.CalledProcessError as e:
        print(f"Backup failed: {e}")
        print(f"Output: {e.stdout}")
        print(f"Error: {e.stderr}")
        return False, None

def drop_all_tables():
    """Drop all tables in the database."""
    print("\n=== Dropping All Tables ===")
    
    # Get DB credentials from .env
    db_name = os.environ.get('DB_NAME', 'ai_ethical_dm')
    db_user = os.environ.get('DB_USER', 'proethica')
    
    try:
        # Generate a SQL file that contains DROP TABLE statements for all tables
        drop_script = """
        DO $$ DECLARE
            r RECORD;
        BEGIN
            -- Disable all triggers
            EXECUTE 'SET session_replication_role = replica';
            
            -- Drop all tables in public schema
            FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
            END LOOP;
            
            -- Re-enable triggers
            EXECUTE 'SET session_replication_role = DEFAULT';
        END $$;
        """
        
        # Write the script to a temporary file
        with open('/tmp/drop_tables.sql', 'w') as f:
            f.write(drop_script)
        
        # Execute the script
        cmd = f"psql -U {db_user} -d {db_name} -f /tmp/drop_tables.sql"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode != 0:
            print(f"Error dropping tables: {result.stderr}")
            return False
        
        print("All tables have been dropped")
        return True
    
    except Exception as e:
        print(f"Error dropping tables: {e}")
        return False

def recreate_schema():
    """Recreate the database schema using alembic."""
    print("\n=== Recreating Database Schema ===")
    
    try:
        # Run Alembic upgrade to create all tables
        result = subprocess.run(
            ['flask', 'db', 'upgrade'], 
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            print(f"Error recreating schema: {result.stderr}")
            return False
        
        print("Schema has been recreated successfully")
        return True
    
    except Exception as e:
        print(f"Error recreating schema: {e}")
        return False

def initialize_essential_data():
    """Initialize the database with essential data."""
    print("\n=== Initializing Essential Data ===")
    
    try:
        # Create admin user
        admin_result = subprocess.run(
            ['python', 'scripts/create_admin_user.py'],
            capture_output=True, text=True
        )
        
        if admin_result.returncode != 0:
            print(f"Warning: Could not create admin user: {admin_result.stderr}")
        else:
            print("Admin user created")
        
        # Initialize other essential data if needed
        # ...
        
        return True
    
    except Exception as e:
        print(f"Error initializing data: {e}")
        return False

def enable_extensions():
    """Enable required PostgreSQL extensions."""
    print("\n=== Enabling PostgreSQL Extensions ===")
    
    try:
        # Enable pgvector
        pgvector_result = subprocess.run(
            ['psql', '-f', 'scripts/enable_pgvector.sql'],
            capture_output=True, text=True
        )
        
        if pgvector_result.returncode != 0:
            print(f"Warning: Could not enable pgvector: {pgvector_result.stderr}")
        else:
            print("pgvector extension enabled")
        
        return True
    
    except Exception as e:
        print(f"Error enabling extensions: {e}")
        return False

def main():
    """Run the database recreation process."""
    parser = argparse.ArgumentParser(description='Recreate a clean database')
    parser.add_argument('--no-backup', action='store_true', help='Skip creating a backup')
    parser.add_argument('--force', action='store_true', help='Do not ask for confirmation')
    args = parser.parse_args()
    
    print("=== Database Recreation Tool ===")
    
    # Ask for confirmation
    if not args.force:
        confirmation = input(
            "\n⚠️  WARNING: This will delete ALL data in the database. ⚠️\n"
            "Are you sure you want to continue? This action cannot be undone.\n"
            "Enter 'yes' to confirm: "
        )
        if confirmation.lower() != 'yes':
            print("Operation cancelled.")
            return
    
    # Create backup
    if not args.no_backup:
        backup_success, backup_file = create_backup()
        if not backup_success:
            if not args.force:
                print("Backup failed and --force not specified. Aborting.")
                return
            print("Continuing without backup...")
    
    # Record start time
    start_time = time.time()
    
    # Main operations
    success = (
        drop_all_tables() and
        enable_extensions() and
        recreate_schema() and
        initialize_essential_data()
    )
    
    # Record end time
    end_time = time.time()
    duration = end_time - start_time
    
    print("\n=== Operation Summary ===")
    if success:
        print(f"✅ Database successfully recreated in {duration:.2f} seconds")
        if not args.no_backup:
            print(f"A backup was created at: {backup_file}")
    else:
        print("❌ Database recreation failed - check the errors above")
    
    print("\nTo restore the database to its previous state, run:")
    print(f"bash backups/restore_database.sh {os.path.basename(backup_file).replace('.dump', '')}")

if __name__ == "__main__":
    main()
