#!/usr/bin/env python3
"""
Migration: Add Temporal Columns to Actions Table

Adds the temporal_boundaries, temporal_relations, and process_profile columns
to the actions table that were added in Phase 4 temporal reasoning implementation.

These columns are needed for the enhanced scenario generation with LLM-mediated
temporal reasoning functionality.
"""

import os
import sys
import logging
from sqlalchemy import text

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Set the database URI environment variable directly
os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://proethica_user:proethica_development_password@localhost:5432/ai_ethical_dm'

# Add project root to path so we can import from app
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Run the temporal columns migration."""
    
    app = create_app(Config)
    
    with app.app_context():
        try:
            logger.info("Starting temporal columns migration...")
            
            # Check if columns already exist
            check_sql = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'actions' 
            AND column_name IN ('temporal_boundaries', 'temporal_relations', 'process_profile');
            """
            
            result = db.session.execute(text(check_sql))
            existing_columns = [row[0] for row in result.fetchall()]
            
            logger.info(f"Existing temporal columns: {existing_columns}")
            
            # Add missing columns
            columns_to_add = {
                'temporal_boundaries': 'JSON',
                'temporal_relations': 'JSON', 
                'process_profile': 'JSON'
            }
            
            for column_name, column_type in columns_to_add.items():
                if column_name not in existing_columns:
                    alter_sql = f"ALTER TABLE actions ADD COLUMN {column_name} {column_type};"
                    logger.info(f"Adding column: {column_name}")
                    db.session.execute(text(alter_sql))
                else:
                    logger.info(f"Column {column_name} already exists, skipping")
            
            # Also check events table (might need same columns)
            check_events_sql = """
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'events' 
            AND column_name IN ('temporal_boundaries', 'temporal_relations', 'process_profile');
            """
            
            result = db.session.execute(text(check_events_sql))
            existing_event_columns = [row[0] for row in result.fetchall()]
            
            logger.info(f"Existing event temporal columns: {existing_event_columns}")
            
            # Add missing columns to events table if needed
            for column_name, column_type in columns_to_add.items():
                if column_name not in existing_event_columns:
                    alter_sql = f"ALTER TABLE events ADD COLUMN {column_name} {column_type};"
                    logger.info(f"Adding column to events: {column_name}")
                    db.session.execute(text(alter_sql))
                else:
                    logger.info(f"Events column {column_name} already exists, skipping")
            
            db.session.commit()
            logger.info("✅ Temporal columns migration completed successfully")
            
            # Verify the changes
            verify_sql = """
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name IN ('actions', 'events')
            AND column_name IN ('temporal_boundaries', 'temporal_relations', 'process_profile')
            ORDER BY table_name, column_name;
            """
            
            result = db.session.execute(text(verify_sql))
            verification = result.fetchall()
            
            logger.info("Verification - Added columns:")
            for row in verification:
                logger.info(f"  {row[0]}: {row[1]}")
                
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    run_migration()
