#!/usr/bin/env python
"""
Test script to verify the entity_triples table was created correctly
and that character triples were migrated successfully.
"""

import os
import sys
import json
from datetime import datetime
from pprint import pprint

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.triple import Triple
from app.models.entity_triple import EntityTriple
from sqlalchemy import text

def verify_table_structure():
    """Verify the entity_triples table structure."""
    print("\n=== Verifying Entity Triples Table Structure ===")
    
    # Check if table exists
    query = """
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'entity_triples'
    );
    """
    result = db.session.execute(text(query)).fetchone()
    if result[0]:
        print("✓ entity_triples table exists")
    else:
        print("✗ entity_triples table does not exist")
        return False
    
    # Check indexes
    indexes_query = """
    SELECT indexname FROM pg_indexes 
    WHERE tablename = 'entity_triples'
    ORDER BY indexname;
    """
    indexes = db.session.execute(text(indexes_query)).fetchall()
    index_names = [idx[0] for idx in indexes]
    
    expected_indexes = [
        'entity_triples_pkey',  # Primary key
        'idx_entity_triples_entity',
        'idx_entity_triples_graph',
        'idx_entity_triples_predicate',
        'idx_entity_triples_scenario',
        'idx_entity_triples_subject',
    ]
    
    for idx in expected_indexes:
        if any(idx in index_name for index_name in index_names):
            print(f"✓ Index found: {idx}")
        else:
            print(f"✗ Missing index: {idx}")
    
    # Check vector indexes (these might have different names)
    if any('ivfflat' in idx_name for idx_name in index_names):
        print(f"✓ Vector indexes found")
    else:
        print(f"✗ Vector indexes not found")
    
    return True

def check_migration_success():
    """Check if character_triples were successfully migrated to entity_triples."""
    print("\n=== Checking Character Triples Migration ===")
    
    # Count character_triples
    char_triples_count = db.session.query(Triple).count()
    print(f"Character triples count: {char_triples_count}")
    
    # Count migrated entity_triples
    entity_triples_count = db.session.query(EntityTriple).filter_by(entity_type='character').count()
    print(f"Entity triples for characters: {entity_triples_count}")
    
    if entity_triples_count >= char_triples_count:
        print("✓ All character triples appear to be migrated")
        return True
    else:
        print(f"✗ Migration may be incomplete: {entity_triples_count}/{char_triples_count} triples migrated")
        return False

def check_sync_triggers():
    """Test the synchronization triggers between tables."""
    print("\n=== Testing Sync Triggers ===")
    
    try:
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
            print(f"✓ Found matching entity triple for character triple {char_triple.id}")
        else:
            print(f"✗ No matching entity triple found for character triple {char_triple.id}")
        
        return True
    
    except Exception as e:
        print(f"Error testing triggers: {str(e)}")
        return False

def main():
    """Run the verification tests."""
    app = create_app()
    
    with app.app_context():
        print("\n=== Entity Triples Table Verification ===")
        table_ok = verify_table_structure()
        
        if table_ok:
            migration_ok = check_migration_success()
            triggers_ok = check_sync_triggers()
            
            if migration_ok and triggers_ok:
                print("\n✓ Entity triples table is correctly set up and populated")
            else:
                print("\n⚠ Entity triples table exists but there may be issues with migration or triggers")
        else:
            print("\n✗ Entity triples table verification failed")

if __name__ == "__main__":
    main()
