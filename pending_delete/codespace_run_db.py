#!/usr/bin/env python3
"""
Database check and initialization script for ProEthica in Codespace

This script performs these key functions:
1. Check database connection
2. Initialize the database if needed
3. Import essential test data if needed
"""

import os
import sys
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from urllib.parse import urlparse
import time

# Set up logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Default database connection string for Codespace
DEFAULT_DB_URL = 'postgresql://postgres:PASS@localhost:5433/postgres'
TARGET_DB_URL = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'

def wait_for_postgres(db_url, max_retries=5, retry_interval=2):
    """Wait for PostgreSQL to become available"""
    url = urlparse(db_url)
    retries = 0
    
    while retries < max_retries:
        try:
            logger.info(f"Attempting to connect to PostgreSQL (attempt {retries+1}/{max_retries})...")
            conn = psycopg2.connect(
                dbname=url.path[1:] if url.path and url.path != '/' else 'postgres',
                user=url.username,
                password=url.password,
                host=url.hostname,
                port=url.port or 5432,
                connect_timeout=3
            )
            conn.close()
            logger.info("Successfully connected to PostgreSQL!")
            return True
        except Exception as e:
            logger.warning(f"Could not connect to PostgreSQL: {e}")
            retries += 1
            if retries < max_retries:
                logger.info(f"Retrying in {retry_interval} seconds...")
                time.sleep(retry_interval)
    
    logger.error(f"Failed to connect to PostgreSQL after {max_retries} attempts")
    return False

def create_database_if_not_exists():
    """Create the ai_ethical_dm database if it doesn't exist"""
    try:
        # Connect to default database
        conn = psycopg2.connect(DEFAULT_DB_URL)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if our database exists
        cursor.execute("SELECT 1 FROM pg_database WHERE datname = 'ai_ethical_dm'")
        if not cursor.fetchone():
            logger.info("Creating ai_ethical_dm database...")
            cursor.execute("CREATE DATABASE ai_ethical_dm")
            logger.info("Database created successfully")
        else:
            logger.info("Database ai_ethical_dm already exists")
            
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error creating database: {e}")
        return False

def initialize_database():
    """Initialize database with basic schema if needed"""
    try:
        # Connect to our database
        logger.info("Connecting to ai_ethical_dm database...")
        conn = psycopg2.connect(TARGET_DB_URL)
        cursor = conn.cursor()
        
        # Check if the database has basic tables by checking for ontologies table
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'ontologies'
            )
        """)
        has_tables = cursor.fetchone()[0]
        
        if not has_tables:
            logger.info("Database is empty, running initialization scripts...")
            # Add very minimal schema to get started - the full app will create the rest
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ontologies (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL UNIQUE,
                    description TEXT,
                    file_path VARCHAR(255)
                );
                
                CREATE TABLE IF NOT EXISTS entity_triples (
                    id SERIAL PRIMARY KEY,
                    subject VARCHAR(255) NOT NULL,
                    predicate VARCHAR(255) NOT NULL,
                    object TEXT NOT NULL,
                    is_literal BOOLEAN DEFAULT FALSE,
                    ontology_id INTEGER REFERENCES ontologies(id)
                );
                
                -- Add a sample ontology for testing
                INSERT INTO ontologies (name, description, file_path)
                VALUES ('test', 'Test ontology for development', 'test.ttl');
            """)
            conn.commit()
            logger.info("Basic schema created successfully")
        else:
            logger.info("Database already has tables, skipping initialization")
            
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False

def main():
    """Main function to check and initialize the database"""
    logger.info("Starting database check and initialization...")
    
    # Wait for PostgreSQL to become available
    if not wait_for_postgres(DEFAULT_DB_URL):
        logger.error("Could not connect to PostgreSQL, exiting")
        sys.exit(1)
    
    # Create database if needed
    if not create_database_if_not_exists():
        logger.error("Failed to create database, exiting")
        sys.exit(1)
    
    # Initialize database if needed
    if not initialize_database():
        logger.error("Failed to initialize database, exiting")
        sys.exit(1)
    
    logger.info("Database check and initialization completed successfully")
    
    # Create a success file that other scripts can check
    with open('.db_initialized', 'w') as f:
        f.write(f"Database initialization completed at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
