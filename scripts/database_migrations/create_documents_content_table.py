#!/usr/bin/env python3
"""
Create Documents Content Table
------------------------------
Creates the missing documents_content table needed for storing NSPE case content.

This script addresses the error:
"relation 'documents_content' does not exist"

Usage:
    python scripts/database_migrations/create_documents_content_table.py
"""

import os
import sys
import logging
import psycopg2
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("create_documents_content_table")

# Import database connection parameters
DB_PARAMS = {
    "dbname": "ai_ethical_dm",
    "user": "postgres",
    "password": "PASS",
    "host": "localhost",
    "port": "5433"
}

# Try to load from project config if possible
try:
    sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "nspe-pipeline"))
    from config import DB_PARAMS as CONFIG_DB_PARAMS
    DB_PARAMS = CONFIG_DB_PARAMS
    logger.info("Successfully loaded database parameters from config.py")
except ImportError:
    logger.warning("Could not import config.py; using default database parameters")

def get_db_connection():
    """Create a connection to the database."""
    try:
        logger.debug(f"Connecting to database: {DB_PARAMS['dbname']} on {DB_PARAMS['host']}:{DB_PARAMS['port']}")
        conn = psycopg2.connect(**DB_PARAMS)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        return None

def create_documents_content_table():
    """Create the documents_content table."""
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        # Create a cursor
        cur = conn.cursor()
        
        # Check if the table already exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'documents_content'
            );
        """)
        
        if cur.fetchone()[0]:
            logger.info("documents_content table already exists.")
            return True
        
        # Create the documents_content table
        logger.info("Creating documents_content table...")
        cur.execute("""
            CREATE TABLE documents_content (
                id SERIAL PRIMARY KEY,
                document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                description TEXT,
                decision TEXT,
                outcome TEXT,
                ethical_analysis TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT now(),
                updated_at TIMESTAMP NOT NULL DEFAULT now()
            );
            
            -- Create an index on document_id for faster lookups
            CREATE INDEX idx_documents_content_document_id ON documents_content(document_id);
            
            -- Comment on table
            COMMENT ON TABLE documents_content IS 'Stores the detailed content sections for documents';
        """)
        
        conn.commit()
        logger.info("documents_content table created successfully.")
        
        # Close the cursor and connection
        cur.close()
        conn.close()
        
        return True
    
    except Exception as e:
        logger.error(f"Error creating documents_content table: {str(e)}")
        
        # Rollback transaction if an error occurred
        if 'conn' in locals() and conn:
            conn.rollback()
            
            # Close connections
            if 'cur' in locals() and cur:
                cur.close()
                
            conn.close()
            
        return False

if __name__ == "__main__":
    success = create_documents_content_table()
    
    if success:
        logger.info("Database migration completed successfully.")
        sys.exit(0)
    else:
        logger.error("Database migration failed.")
        sys.exit(1)
