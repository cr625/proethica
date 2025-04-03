#!/usr/bin/env python
"""
Script to run the entity_triples table migration and test the implementation.
This script will:
1. Run the SQL migration script to create the entity_triples table
2. Test the migration of character triples to entity_triples
"""

import os
import sys
import argparse
from datetime import datetime
from pprint import pprint

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from sqlalchemy import text

def run_sql_script(script_path):
    """Run a SQL script file."""
    print(f"Running SQL script: {script_path}")
    
    with open(script_path, 'r') as f:
        sql = f.read()
    
    # Execute the script in parts to better handle errors
    # Split on semicolons but respect those in quotes and function bodies
    statements = []
    current_statement = []
    in_function_body = False
    
    for line in sql.splitlines():
        line = line.strip()
        
        # Skip comments and empty lines when building statements
        if line.startswith('--') or not line:
            continue
        
        # Track function body
        if 'FUNCTION' in line.upper() and 'RETURNS' in line.upper():
            in_function_body = True
        
        current_statement.append(line)
        
        # End of function body
        if in_function_body and line.startswith('$$'):
            in_function_body = False
        
        # End of statement if not in function body
        if line.endswith(';') and not in_function_body:
            statements.append(' '.join(current_statement))
            current_statement = []
    
    # Add any remaining statement
    if current_statement:
        statements.append(' '.join(current_statement))
    
    # Execute each statement
    for i, statement in enumerate(statements):
        if not statement.strip():
            continue
            
        try:
            print(f"Executing statement {i+1}/{len(statements)}...")
            db.session.execute(text(statement))
            db.session.commit()
        except Exception as e:
            print(f"Error executing statement: {e}")
            db.session.rollback()
            
            # Print the problematic statement
            print(f"Problematic statement: {statement}")
            
            # Ask user if they want to continue
            if not args.force:
                response = input("Continue? (y/n): ")
                if response.lower() != 'y':
                    return False
    
    return True

def test_migration():
    """Test that the migration was successful."""
    from app.models.triple import Triple
    from app.models.entity_triple import EntityTriple
    
    # Check if entity_triples table exists
    check_query = """
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'entity_triples'
    );
    """
    result = db.session.execute(text(check_query)).fetchone()
    
    if not result[0]:
        print("entity_triples table does not exist!")
        return False
    
    print("entity_triples table exists!")
    
    # Check if character triples were migrated
    char_triples_count = db.session.query(Triple).count()
    entity_triples_count = db.session.query(EntityTriple).filter_by(entity_type='character').count()
    
    print(f"Character triples count: {char_triples_count}")
    print(f"Entity triples for characters: {entity_triples_count}")
    
    if entity_triples_count >= char_triples_count:
        print("All character triples appear to be migrated!")
        return True
    else:
        print(f"Migration incomplete: {entity_triples_count}/{char_triples_count} triples migrated.")
        return False

def test_sync_triggers():
    """Test the synchronization triggers between tables."""
    from app.models.triple import Triple
    from app.models.entity_triple import EntityTriple
    
    # Find a character triple to use for testing
    char_triple = db.session.query(Triple).first()
    if not char_triple:
        print("No character triples found for testing triggers")
        return False
    
    # Check if a corresponding entity triple exists
    entity_triple = db.session.query(EntityTriple).filter_by(
        entity_type='character', 
        entity_id=char_triple.character_id,
        predicate=char_triple.predicate
    ).first()
    
    if entity_triple:
        print(f"Found matching entity triple for character triple {char_triple.id}")
        return True
    else:
        print(f"No matching entity triple found for character triple {char_triple.id}")
        return False

def backup_database():
    """Create a backup of the database before migration."""
    import subprocess
    from datetime import datetime
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = f"backup_before_entity_triples_{timestamp}.dump"
    
    # Check if backups directory exists, create if not
    if not os.path.exists('backups'):
        os.makedirs('backups')
    
    backup_path = os.path.join('backups', backup_file)
    
    # Get database info from environment or config
    from app.config import Config
    db_uri = Config.SQLALCHEMY_DATABASE_URI
    
    # Parse database name from URI
    db_name = db_uri.split('/')[-1]
    
    print(f"Creating backup of database {db_name} to {backup_path}...")
    
    try:
        subprocess.run(['pg_dump', '-Fc', '-f', backup_path, db_name], check=True)
        print(f"Backup created successfully: {backup_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error creating backup: {e}")
        return False

def main(args):
    """Run the migration and tests."""
    app = create_app()
    
    with app.app_context():
        # Create a backup if requested
        if args.backup:
            if not backup_database():
                if not args.force:
                    print("Backup failed. Aborting.")
                    return
                print("Backup failed but continuing due to --force flag.")
        
        # Run the SQL migration script
        script_path = os.path.join('scripts', 'create_entity_triples_table.sql')
        if not os.path.exists(script_path):
            print(f"SQL script not found: {script_path}")
            return
        
        success = run_sql_script(script_path)
        if not success:
            print("Migration failed.")
            return
        
        # Test the migration
        print("\nTesting migration...")
        migration_success = test_migration()
        
        # Test the sync triggers
        print("\nTesting sync triggers...")
        triggers_success = test_sync_triggers()
        
        if migration_success and triggers_success:
            print("\nMigration completed successfully!")
        else:
            print("\nMigration completed with issues.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run entity_triples migration and tests')
    parser.add_argument('--force', action='store_true', help='Continue even if errors occur')
    parser.add_argument('--backup', action='store_true', help='Create a database backup before migration')
    args = parser.parse_args()
    
    main(args)
