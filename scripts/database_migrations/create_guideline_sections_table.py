#!/usr/bin/env python3
"""
Database migration script to create guideline_sections table.

This migration adds structured section support for guidelines documents,
enabling precise referencing of individual sections like [I.1], [II.1.c], etc.

Usage:
    python scripts/database_migrations/create_guideline_sections_table.py
"""

import os
import sys
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from pathlib import Path
from dotenv import load_dotenv

# Add the project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
load_dotenv(project_root / '.env')

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get database connection parameters from environment variables
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '5433')
DB_NAME = os.getenv('DB_NAME', 'ai_ethical_dm')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'PASS')

def create_connection():
    """Create a database connection to the PostgreSQL database."""
    conn = None
    try:
        # Parse DATABASE_URL if available
        database_url = os.getenv('DATABASE_URL')
        if database_url:
            conn = psycopg2.connect(database_url)
        else:
            conn = psycopg2.connect(
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME,
                user=DB_USER,
                password=DB_PASSWORD
            )
        
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        logger.info("Database connection established")
        return conn
    except psycopg2.Error as e:
        logger.error(f"Error connecting to database: {e}")
        return None

def read_migration_sql():
    """Read the SQL migration file."""
    sql_file = project_root / "migrations" / "create_guideline_sections_table.sql"
    
    if not sql_file.exists():
        raise FileNotFoundError(f"Migration SQL file not found: {sql_file}")
    
    with open(sql_file, 'r') as f:
        return f.read()

def check_table_exists(conn):
    """Check if guideline_sections table already exists."""
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'guideline_sections'
            );
        """)
        result = cursor.fetchone()[0]
        cursor.close()
        return result
    except Exception as e:
        logger.error(f"Error checking if table exists: {e}")
        return False

def run_migration(conn):
    """Execute the database migration."""
    try:
        # Check if table already exists
        if check_table_exists(conn):
            logger.info("guideline_sections table already exists. Skipping migration.")
            return True
        
        logger.info("Creating guideline_sections table...")
        
        # Read and execute the migration SQL
        migration_sql = read_migration_sql()
        cursor = conn.cursor()
        cursor.execute(migration_sql)
        cursor.close()
        
        logger.info("✅ Successfully created guideline_sections table")
        
        # Verify the table was created
        if check_table_exists(conn):
            logger.info("✅ Table creation verified")
            return True
        else:
            logger.error("❌ Table creation verification failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        return False

def main():
    """Main migration execution."""
    logger.info("Starting guideline_sections table migration...")
    
    # Create database connection
    conn = create_connection()
    if not conn:
        logger.error("💥 Failed to connect to database!")
        sys.exit(1)
    
    try:
        # Run the migration
        success = run_migration(conn)
        
        if success:
            logger.info("🎉 Migration completed successfully!")
            sys.exit(0)
        else:
            logger.error("💥 Migration failed!")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"💥 Unexpected error during migration: {e}")
        sys.exit(1)
    finally:
        # Close database connection
        if conn:
            conn.close()
            logger.info("Database connection closed")

if __name__ == "__main__":
    main()