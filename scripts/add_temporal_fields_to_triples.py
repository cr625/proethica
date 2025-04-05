#!/usr/bin/env python
"""
Script to add temporal fields to the entity_triples table.

This script adds BFO-compatible temporal fields to support advanced
temporal representation and reasoning in the triple-based structure.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db, create_app
from sqlalchemy import text
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def add_temporal_fields():
    """Add BFO-based temporal fields to the entity_triples table."""
    try:
        # Check if columns already exist
        inspector = db.inspect(db.engine)
        columns = [column['name'] for column in inspector.get_columns('entity_triples')]
        
        # Skip if all columns already exist
        if ('temporal_region_type' in columns and 
            'temporal_start' in columns and 
            'temporal_end' in columns and 
            'temporal_relation_type' in columns and 
            'temporal_relation_to' in columns and 
            'temporal_granularity' in columns):
            logger.info("Temporal fields already exist in entity_triples table. Skipping.")
            return
        
        logger.info("Adding temporal fields to entity_triples table...")
        
        # Add columns
        commands = [
            "ALTER TABLE entity_triples ADD COLUMN IF NOT EXISTS temporal_region_type VARCHAR(255)",
            "ALTER TABLE entity_triples ADD COLUMN IF NOT EXISTS temporal_start TIMESTAMP",
            "ALTER TABLE entity_triples ADD COLUMN IF NOT EXISTS temporal_end TIMESTAMP",
            "ALTER TABLE entity_triples ADD COLUMN IF NOT EXISTS temporal_relation_type VARCHAR(50)",
            "ALTER TABLE entity_triples ADD COLUMN IF NOT EXISTS temporal_relation_to INTEGER",
            "ALTER TABLE entity_triples ADD COLUMN IF NOT EXISTS temporal_granularity VARCHAR(50)"
        ]
        
        for command in commands:
            db.session.execute(text(command))
        
        # Add foreign key constraint - check if it exists first
        constraint_exists = db.session.execute(text("""
            SELECT 1 FROM pg_constraint 
            WHERE conname = 'fk_temporal_relation' 
            AND conrelid = 'entity_triples'::regclass
        """)).scalar() is not None
        
        if not constraint_exists:
            db.session.execute(text("""
                ALTER TABLE entity_triples 
                ADD CONSTRAINT fk_temporal_relation 
                FOREIGN KEY (temporal_relation_to) 
                REFERENCES entity_triples(id)
            """))
        
        # Check if index exists
        index_exists = db.session.execute(text("""
            SELECT 1 FROM pg_indexes 
            WHERE indexname = 'idx_entity_triples_temporal'
        """)).scalar() is not None
        
        # Create index for temporal queries if it doesn't exist
        if not index_exists:
            db.session.execute(text("""
                CREATE INDEX idx_entity_triples_temporal 
                ON entity_triples(temporal_start, temporal_end)
            """))
        
        db.session.commit()
        logger.info("Temporal fields added successfully!")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error adding temporal fields: {str(e)}")
        raise

def main():
    """Main execution function."""
    try:
        # Create the Flask app and push an application context
        app = create_app()
        with app.app_context():
            add_temporal_fields()
            logger.info("Migration completed successfully.")
    except Exception as e:
        logger.error(f"Migration failed: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
