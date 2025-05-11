#!/usr/bin/env python3
"""
Database Schema Verification Script for ProEthica.

This lightweight script verifies that all required database tables exist in the PostgreSQL database
without initializing the full application context. This avoids the redundant initialization that
occurs when running the full initialize_proethica_db.py script.
"""

import os
import sys
from sqlalchemy import create_engine, inspect

# Get the database URL from .env file if possible
def get_db_url_from_env():
    """Extract the database URL from .env file."""
    try:
        if os.path.exists('.env'):
            with open('.env', 'r') as env_file:
                for line in env_file:
                    if line.strip().startswith('DATABASE_URL='):
                        return line.strip().split('=', 1)[1].strip()
    except Exception as e:
        print(f"Warning: Error reading .env file: {e}")
    
    # Default fallback
    return 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'

# Set the database URL 
os.environ['DATABASE_URL'] = get_db_url_from_env()

def check_database_schema():
    """Check if the required database tables exist without initializing the full app."""
    print("Verifying ProEthica database schema...")
    
    # Create engine directly
    engine = create_engine(os.environ['DATABASE_URL'])
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    
    # Check tables
    expected_tables = [
        'users', 'worlds', 'scenarios', 'entities', 
        'characters', 'documents', 'ontologies', 'entity_triples',
        'roles', 'resource_types', 'condition_types', 'conditions', 
        'resources', 'event_entity', 'evaluations', 'actions', 
        'events', 'decisions', 'document_chunks', 'simulation_sessions',
        'simulation_states', 'character_triples', 'ontology_versions', 'ontology_imports'
    ]
    
    all_tables_exist = True
    missing_tables = []
    
    for table in expected_tables:
        if table in tables:
            print(f"✅ Table '{table}' exists")
        else:
            print(f"❌ Table '{table}' is missing")
            all_tables_exist = False
            missing_tables.append(table)
    
    return all_tables_exist, missing_tables

if __name__ == "__main__":
    print("\nVerifying database tables:")
    all_tables_exist, missing_tables = check_database_schema()
    
    if all_tables_exist:
        print("\nDatabase schema verification complete. All required tables exist.")
        sys.exit(0)
    else:
        print(f"\nSome required tables are missing: {', '.join(missing_tables)}")
        print("You should run the full database initialization.")
        sys.exit(1)
