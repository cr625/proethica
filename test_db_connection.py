#!/usr/bin/env python3
"""
Test script for direct database connection.
This script tests our fix for the SQL error in the MCP server.
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

def test_direct_connection():
    """Test direct SQLAlchemy connection to the database."""
    # Get database URL from environment variable with fallback
    database_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    print(f"Using database URL: {database_url}")
    
    try:
        # Create SQLAlchemy engine and session
        engine = create_engine(database_url)
        Session = sessionmaker(bind=engine)
        session = Session()
        
        # Test connection with a simple query
        result = session.execute(text("SELECT current_database(), current_user"))
        db_info = result.fetchone()
        print(f"Connected to database: {db_info[0]} as user: {db_info[1]}")
        
        # Look for ontologies table (correct table name)
        result = session.execute(text("SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = 'ontologies')"))
        has_ontologies_table = result.scalar()
        
        if has_ontologies_table:
            print("Ontologies table exists")
            
            # Check the schema of the ontologies table
            result = session.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'ontologies' ORDER BY ordinal_position"))
            columns = result.fetchall()
            print("\nOntologies table schema:")
            for column in columns:
                print(f"  - {column[0]} ({column[1]})")
            
            # Query for engineering_ethics domain in the ontologies table
            result = session.execute(text("SELECT id, domain_id, name FROM ontologies WHERE domain_id = :domain_id"), 
                                   {"domain_id": "engineering_ethics"})
            row = result.fetchone()
            
            if row:
                ontology_id, domain_id, name = row
                print(f"Found ontology '{domain_id}' (ID: {ontology_id}, Name: {name})")
                
                # Count triples
                result = session.execute(text("SELECT COUNT(*) FROM ontology_triples WHERE ontology_id = :id"), 
                                      {"id": ontology_id})
                triple_count = result.scalar()
                print(f"Ontology has {triple_count} triples")
            else:
                print("No engineering_ethics ontology found in database")
                
                # List available ontologies
                result = session.execute(text("SELECT id, domain_id, name FROM ontologies LIMIT 5"))
                rows = result.fetchall()
                if rows:
                    print("Available ontologies:")
                    for row in rows:
                        print(f"  - {row[1]} (ID: {row[0]}, Name: {row[2]})")
                else:
                    print("No ontologies found in database")
        else:
            print("Ontology table does not exist!")
            
            # List all tables
            result = session.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'"))
            rows = result.fetchall()
            print("Available tables:")
            for row in rows:
                print(f"  - {row[0]}")
        
        # Close the session
        session.close()
        print("Database connection test completed successfully")
        return True
        
    except Exception as e:
        print(f"Database connection error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== Testing Direct Database Connection ===\n")
    if test_direct_connection():
        print("\nSUCCESS: Database connection working correctly!")
    else:
        print("\nFAILURE: Database connection test failed.")
        sys.exit(1)
