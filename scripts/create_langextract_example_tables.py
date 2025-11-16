#!/usr/bin/env python3
"""
Create database tables for LangExtract example management.

This script creates the new tables needed for storing and managing
LangExtract examples in the prompt builder system.
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app import create_app
from app.models import db
from app.models.prompt_templates import LangExtractExample, LangExtractExampleExtraction
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_tables():
    """Create the new LangExtract example tables."""
    try:
        app = create_app()
        with app.app_context():
            logger.info("Creating LangExtract example tables...")
            
            # Create the tables
            db.create_all()
            
            logger.info("Tables created successfully!")
            
            # Verify tables exist
            from sqlalchemy import text
            
            # Check langextract_examples table
            result = db.session.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_name = 'langextract_examples'
            """))
            examples_exists = result.scalar() > 0
            logger.info(f"langextract_examples table exists: {examples_exists}")
            
            # Check langextract_example_extractions table  
            result = db.session.execute(text("""
                SELECT COUNT(*) FROM information_schema.tables 
                WHERE table_name = 'langextract_example_extractions'
            """))
            extractions_exists = result.scalar() > 0
            logger.info(f"langextract_example_extractions table exists: {extractions_exists}")
            
            if examples_exists and extractions_exists:
                logger.info("All LangExtract example tables created successfully!")
                return True
            else:
                logger.error("Failed to create some tables")
                return False
                
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        return False

if __name__ == "__main__":
    success = create_tables()
    if success:
        print("Database tables created successfully!")
        sys.exit(0)
    else:
        print("Failed to create database tables")
        sys.exit(1)