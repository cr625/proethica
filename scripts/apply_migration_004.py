#!/usr/bin/env python3
"""
Apply Migration 004: Add two-tier concept mapping fields
"""

import os
import sys

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask
from app.models import db
from app.config import Config

def create_app():
    """Create Flask app for database operations."""
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app

def apply_migration():
    """Apply the migration SQL."""
    
    migration_sql = """
    -- Add new columns to entity_triples table
    ALTER TABLE entity_triples 
    ADD COLUMN IF NOT EXISTS semantic_label VARCHAR(255),
    ADD COLUMN IF NOT EXISTS primary_type VARCHAR(255),
    ADD COLUMN IF NOT EXISTS mapping_source VARCHAR(50);

    -- Create indexes on new columns for efficient querying
    CREATE INDEX IF NOT EXISTS idx_entity_triples_primary_type ON entity_triples(primary_type);
    CREATE INDEX IF NOT EXISTS idx_entity_triples_semantic_label ON entity_triples(semantic_label);
    CREATE INDEX IF NOT EXISTS idx_entity_triples_mapping_source ON entity_triples(mapping_source);

    -- Backfill existing data: migrate object_literal to primary_type for type triples
    UPDATE entity_triples 
    SET primary_type = object_literal,
        mapping_source = 'legacy'
    WHERE predicate = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type' 
      AND object_literal IN ('Role', 'Principle', 'Obligation', 'State', 'Resource', 'Action', 'Event', 'Capability')
      AND primary_type IS NULL;

    -- Set semantic_label from original_llm_type where available
    UPDATE entity_triples 
    SET semantic_label = original_llm_type
    WHERE original_llm_type IS NOT NULL 
      AND predicate = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
      AND semantic_label IS NULL;
    """
    
    try:
        print("🔄 Applying Migration 004: Two-tier concept mapping...")
        
        # Execute the migration
        db.session.execute(db.text(migration_sql))
        db.session.commit()
        
        print("✅ Migration 004 applied successfully!")
        
        # Verify the changes
        result = db.session.execute(db.text("""
            SELECT COUNT(*) as total_records,
                   COUNT(semantic_label) as with_semantic_label,
                   COUNT(primary_type) as with_primary_type,
                   COUNT(mapping_source) as with_mapping_source
            FROM entity_triples 
            WHERE predicate = 'http://www.w3.org/1999/02/22-rdf-syntax-ns#type'
        """)).fetchone()
        
        print(f"📊 Migration verification:")
        print(f"   - Total type triples: {result.total_records}")
        print(f"   - With semantic_label: {result.with_semantic_label}")
        print(f"   - With primary_type: {result.with_primary_type}")
        print(f"   - With mapping_source: {result.with_mapping_source}")
        
        return True
        
    except Exception as e:
        db.session.rollback()
        print(f"❌ Migration failed: {str(e)}")
        return False

def main():
    app = create_app()
    
    with app.app_context():
        success = apply_migration()
        if not success:
            sys.exit(1)

if __name__ == '__main__':
    main()