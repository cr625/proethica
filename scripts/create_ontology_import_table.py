#!/usr/bin/env python3
"""
Create the ontology_imports table and add new columns to the ontologies table.

This script adds:
1. The ontology_imports table to track import relationships
2. is_base field to ontologies to flag base ontologies
3. is_editable field to ontologies to control editing
4. base_uri field to ontologies to store the canonical URI
"""

import sys
import os
import logging
from sqlalchemy import Column, Integer, ForeignKey, Boolean, String, DateTime, func, Table, MetaData

# Add the parent directory to the path so we can import app correctly
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import db, create_app
from flask_migrate import Migrate

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_ontology_imports_table():
    """Create the ontology_imports table and add new columns to ontologies."""
    try:
        # Configure app without unnecessary services for this script
        os.environ["USE_AGENT_ORCHESTRATOR"] = "false"
        os.environ["USE_CLAUDE"] = "false"
        os.environ["USE_MOCK_FALLBACK"] = "false"  # Disable MCP mock fallback
        
        app = create_app()
        with app.app_context():
            # Get metadata from current database connection
            metadata = MetaData()
            metadata.reflect(bind=db.engine)
            
            # Check if ontologies table exists
            if 'ontologies' not in metadata.tables:
                logger.error("Ontologies table doesn't exist. Run database migrations first.")
                return False
            
            # Check if new columns already exist
            ontologies_table = metadata.tables['ontologies']
            columns_to_add = []
            
            if 'is_base' not in ontologies_table.columns:
                logger.info("Adding is_base column to ontologies table")
                columns_to_add.append(Column('is_base', Boolean, server_default='0'))
            
            if 'is_editable' not in ontologies_table.columns:
                logger.info("Adding is_editable column to ontologies table")
                columns_to_add.append(Column('is_editable', Boolean, server_default='1'))
                
            if 'base_uri' not in ontologies_table.columns:
                logger.info("Adding base_uri column to ontologies table")
                columns_to_add.append(Column('base_uri', String(255)))
                
            # Add new columns to ontologies table if needed
            for column in columns_to_add:
                db.session.execute(f'ALTER TABLE ontologies ADD COLUMN {column.name} {column.type}')
            
            # Check if ontology_imports table already exists
            if 'ontology_imports' not in metadata.tables:
                logger.info("Creating ontology_imports table")
                
                # Create the ontology_imports table
                ontology_imports = Table(
                    'ontology_imports',
                    metadata,
                    Column('id', Integer, primary_key=True),
                    Column('importing_ontology_id', Integer, ForeignKey('ontologies.id', ondelete='CASCADE'), nullable=False),
                    Column('imported_ontology_id', Integer, ForeignKey('ontologies.id', ondelete='CASCADE'), nullable=False),
                    Column('created_at', DateTime, server_default=func.now()),
                )
                
                ontology_imports.create(bind=db.engine)
                logger.info("Successfully created ontology_imports table")
            else:
                logger.info("ontology_imports table already exists")
                
            db.session.commit()
            logger.info("Database changes committed successfully")
            return True
            
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        return False

if __name__ == '__main__':
    if create_ontology_imports_table():
        logger.info("Successfully created ontology import relationships")
    else:
        logger.error("Failed to create ontology import relationships")
        sys.exit(1)
