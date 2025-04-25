#!/usr/bin/env python3
"""
Standalone script to create the ontology_imports table and add columns to ontologies table.

This script does not rely on the Flask app context, making it more reliable
for database migrations.
"""

import sys
import os
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Parse DATABASE_URL from .env file
def parse_database_url():
    """Read and parse DATABASE_URL from .env file."""
    with open(os.path.join(os.path.dirname(__file__), '..', '.env'), 'r') as f:
        for line in f:
            if line.startswith('DATABASE_URL='):
                db_url = line.strip().split('=', 1)[1]
                # Format: postgresql://user:password@host:port/dbname
                parts = db_url.replace('postgresql://', '').split('@')
                auth = parts[0].split(':')
                host_db = parts[1].split('/')
                host_port = host_db[0].split(':')
                
                return {
                    'user': auth[0],
                    'password': auth[1],
                    'host': host_port[0],
                    'port': host_port[1] if len(host_port) > 1 else '5432',
                    'dbname': host_db[1]
                }
    return None

# Get database connection parameters from .env
db_params = parse_database_url()
if db_params:
    DB_NAME = db_params['dbname']
    DB_USER = db_params['user']
    DB_PASSWORD = db_params['password']
    DB_HOST = db_params['host']
    DB_PORT = db_params['port']
else:
    # Fallback to defaults
    DB_NAME = os.environ.get("DB_NAME", "ai_ethical_dm")
    DB_USER = os.environ.get("DB_USER", "postgres")
    DB_PASSWORD = os.environ.get("DB_PASSWORD", "PASS")
    DB_HOST = os.environ.get("DB_HOST", "localhost")
    DB_PORT = os.environ.get("DB_PORT", "5433")
    
logger.info(f"Using database connection: {DB_HOST}:{DB_PORT}/{DB_NAME}")

def get_connection():
    """Get a connection to the database."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise

def check_column_exists(cursor, table, column):
    """Check if a column exists in a table."""
    cursor.execute(f"""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = '{table}' AND column_name = '{column}'
    """)
    return cursor.fetchone() is not None

def check_table_exists(cursor, table):
    """Check if a table exists."""
    cursor.execute(f"""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_name = '{table}'
    """)
    return cursor.fetchone() is not None

def create_tables():
    """Create the ontology_imports table and add columns to ontologies table."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # Check if ontologies table exists
        if not check_table_exists(cursor, 'ontologies'):
            logger.error("Ontologies table doesn't exist. Run database migrations first.")
            return False
        
        # Add columns to ontologies table if they don't exist
        columns_to_add = [
            ("is_base", "BOOLEAN DEFAULT FALSE"),
            ("is_editable", "BOOLEAN DEFAULT TRUE"),
            ("base_uri", "VARCHAR(255)")
        ]
        
        for column_name, column_type in columns_to_add:
            if not check_column_exists(cursor, 'ontologies', column_name):
                logger.info(f"Adding {column_name} column to ontologies table")
                cursor.execute(f"ALTER TABLE ontologies ADD COLUMN {column_name} {column_type}")
        
        # Create ontology_imports table if it doesn't exist
        if not check_table_exists(cursor, 'ontology_imports'):
            logger.info("Creating ontology_imports table")
            cursor.execute("""
                CREATE TABLE ontology_imports (
                    id SERIAL PRIMARY KEY,
                    importing_ontology_id INTEGER NOT NULL REFERENCES ontologies(id) ON DELETE CASCADE,
                    imported_ontology_id INTEGER NOT NULL REFERENCES ontologies(id) ON DELETE CASCADE,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
            logger.info("Successfully created ontology_imports table")
        else:
            logger.info("ontology_imports table already exists")
        
        # Close connection
        cursor.close()
        conn.close()
        
        logger.info("Database changes completed successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    if create_tables():
        logger.info("Successfully created ontology import tables and columns")
    else:
        logger.error("Failed to create ontology import tables and columns")
        sys.exit(1)
