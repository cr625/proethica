#!/usr/bin/env python
"""
Ensure database schema script.
This script ensures that all required tables exist, especially tables that
may be missing due to recent model additions that weren't properly migrated.
"""

import os
import sys
import logging
from sqlalchemy import text, inspect

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def ensure_guidelines_table():
    """Ensure the guidelines table exists."""
    inspector = inspect(db.engine)
    table_exists = 'guidelines' in inspector.get_table_names()
    
    if not table_exists:
        logger.info("Creating missing 'guidelines' table...")
        sql = """
        CREATE TABLE IF NOT EXISTS guidelines (
            id SERIAL PRIMARY KEY,
            world_id INTEGER NOT NULL REFERENCES worlds(id) ON DELETE CASCADE,
            title VARCHAR(255) NOT NULL,
            content TEXT,
            source_url VARCHAR(1024),
            file_path VARCHAR(1024),
            file_type VARCHAR(50),
            embedding FLOAT[],
            guideline_metadata JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_guidelines_world_id ON guidelines(world_id);
        """
        db.session.execute(text(sql))
        db.session.commit()
        logger.info("'guidelines' table created successfully.")
    else:
        logger.info("'guidelines' table already exists.")

def ensure_entity_triples_columns():
    """Ensure all required columns exist in entity_triples table."""
    inspector = inspect(db.engine)
    entity_triples_exists = 'entity_triples' in inspector.get_table_names()
    
    if entity_triples_exists:
        columns = [c['name'] for c in inspector.get_columns('entity_triples')]
        logger.info(f"Existing entity_triples columns: {', '.join(columns)}")
        
        # Define all required columns and their SQL types
        required_columns = {
            'guideline_id': 'INTEGER REFERENCES guidelines(id) ON DELETE CASCADE',
            'subject_label': 'VARCHAR(255)',
            'predicate_label': 'VARCHAR(255)',
            'object_label': 'VARCHAR(255)',
            'temporal_confidence': 'FLOAT DEFAULT 1.0',
            'temporal_context': 'JSONB DEFAULT \'{}\'',
            'world_id': 'INTEGER REFERENCES worlds(id) ON DELETE CASCADE'
        }
        
        # Check and add missing columns
        for column, column_type in required_columns.items():
            if column not in columns:
                logger.info(f"Adding '{column}' column to 'entity_triples' table...")
                sql = f"""
                ALTER TABLE entity_triples ADD COLUMN {column} {column_type};
                """
                db.session.execute(text(sql))
                db.session.commit()
                logger.info(f"'{column}' column added successfully.")
            else:
                logger.info(f"'{column}' column already exists in 'entity_triples' table.")
    else:
        logger.info("'entity_triples' table does not exist. Skipping column checks.")

def main():
    """Main function to ensure all required schema elements exist."""
    logger.info("Checking database schema...")
    
    # Connect to the database
    try:
        # Check for guidelines table
        ensure_guidelines_table()
        
        # Check for required columns in entity_triples
        ensure_entity_triples_columns()
        
        logger.info("Database schema check completed successfully.")
        return 0
    except Exception as e:
        logger.error(f"Error checking/updating database schema: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
