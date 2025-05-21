"""
Migration script to create document_sections table with pgvector support.
Run this script to add the document_sections table to the database.
"""

import os
import sys
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from sqlalchemy import create_engine, text
from flask import Flask

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to the path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Create a Flask app and get the database URI
def create_app():
    app = Flask(__name__)
    app.config.from_object('app.config.DevelopmentConfig')
    return app

def get_db_uri():
    app = create_app()
    return app.config['SQLALCHEMY_DATABASE_URI']

def create_pgvector_extension(conn_string):
    """Create the pgvector extension if it doesn't exist."""
    try:
        # Connect directly with psycopg2 for extension management
        conn = psycopg2.connect(conn_string)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if extension exists
        cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_extension WHERE extname = 'vector');")
        extension_exists = cursor.fetchone()[0]
        
        if not extension_exists:
            logger.info("Creating pgvector extension...")
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            logger.info("pgvector extension created successfully.")
        else:
            logger.info("pgvector extension already exists.")
            
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error creating pgvector extension: {str(e)}")
        raise

def create_document_sections_table(engine):
    """Create the document_sections table if it doesn't exist."""
    try:
        # Check if table exists
        with engine.connect() as conn:
            result = conn.execute(text("SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name = 'document_sections');"))
            table_exists = result.scalar()
            
            # First, drop the table if it exists since we need to recreate it with the proper vector type
            if table_exists:
                logger.info("Dropping existing document_sections table to recreate with vector type...")
                conn.execute(text("DROP TABLE document_sections CASCADE;"))
                conn.commit()
                table_exists = False
                logger.info("Existing table dropped successfully.")
            
            if not table_exists:
                logger.info("Creating document_sections table...")
                conn.execute(text("""
                CREATE TABLE document_sections (
                    id SERIAL PRIMARY KEY,
                    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    section_id VARCHAR(255) NOT NULL,
                    section_type VARCHAR(50) NOT NULL,
                    position INTEGER,
                    content TEXT NOT NULL,
                    embedding vector(1536),
                    section_metadata JSONB,
                    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT document_section_unique UNIQUE(document_id, section_id)
                );
                """))
                
                # Create indexes for better performance
                conn.execute(text("CREATE INDEX idx_document_sections_document_id ON document_sections(document_id);"))
                conn.execute(text("CREATE INDEX idx_document_sections_section_type ON document_sections(section_type);"))
                
                # Commit the changes
                conn.commit()
                
                logger.info("document_sections table created successfully.")
            else:
                logger.info("document_sections table already exists.")
    except Exception as e:
        logger.error(f"Error creating document_sections table: {str(e)}")
        raise

def add_vector_index(engine):
    """
    Add vector index for similarity searches.
    This should be done after data is migrated for better performance.
    """
    try:
        logger.info("Adding vector index for similarity searches...")
        # Use the appropriate index type based on your needs (L2, IP, or cosine)
        with engine.connect() as conn:
            conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_document_sections_embedding_cosine
            ON document_sections
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);
            """))
            conn.commit()
            logger.info("Vector index added successfully.")
    except Exception as e:
        logger.error(f"Error adding vector index: {str(e)}")
        logger.warning("Vector index not created, but we can continue without it for now.")
        # Don't raise an exception here, as this is not critical for functionality

def run_migration():
    """Run the migration to create the document_sections table."""
    db_uri = get_db_uri()
    logger.info(f"Using database URI: {db_uri}")
    
    # Create pgvector extension
    create_pgvector_extension(db_uri)
    
    # Create engine
    engine = create_engine(db_uri)
    
    # Create document_sections table
    create_document_sections_table(engine)
    
    # Add vector index (optional, can be added later after data migration)
    add_vector_index(engine)
    
    logger.info("Migration completed successfully.")

if __name__ == '__main__':
    logger.info("Starting migration...")
    run_migration()
    logger.info("Migration finished.")
