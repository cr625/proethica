#!/usr/bin/env python3
"""
Direct SQL script to create tables needed for storing McLaren's
extensional definition analysis results.

This script bypasses the Flask application and directly executes SQL
to create the required tables.

Usage:
    python scripts/direct_create_mclaren_tables.py
"""

import logging
import psycopg2
import traceback

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("direct_create_mclaren_tables")

# Database connection parameters
DB_PARAMS = {
    "dbname": "ai_ethical_dm",
    "user": "postgres",
    "password": "PASS",
    "host": "localhost",
    "port": "5433"
}

def create_tables():
    """
    Create the tables needed for McLaren's extensional definition analysis.
    """
    try:
        # Connect to the database
        conn = psycopg2.connect(**DB_PARAMS)
        conn.autocommit = False
        cur = conn.cursor()
        
        # Create tables in two steps:
        # 1. First create tables without foreign key constraints
        # 2. Then add foreign key constraints if the documents table exists
        
        # Create principle_instantiations table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS principle_instantiations (
                id SERIAL PRIMARY KEY,
                case_id INTEGER NOT NULL,
                principle_uri TEXT NOT NULL,
                principle_label TEXT,
                fact_text TEXT NOT NULL,
                fact_context TEXT,
                technique_type TEXT,
                confidence FLOAT DEFAULT 0.5,
                is_negative BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS principle_instantiations_case_id_idx ON principle_instantiations (case_id);
            CREATE INDEX IF NOT EXISTS principle_instantiations_principle_uri_idx ON principle_instantiations (principle_uri);
        """)

        logger.info("Created principle_instantiations table")

        # Create principle_conflicts table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS principle_conflicts (
                id SERIAL PRIMARY KEY,
                case_id INTEGER NOT NULL,
                principle1_uri TEXT NOT NULL,
                principle2_uri TEXT NOT NULL,
                principle1_label TEXT,
                principle2_label TEXT,
                resolution_type TEXT,
                override_direction INTEGER DEFAULT 0,
                context TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS principle_conflicts_case_id_idx ON principle_conflicts (case_id);
            CREATE INDEX IF NOT EXISTS principle_conflicts_principle1_uri_idx ON principle_conflicts (principle1_uri);
            CREATE INDEX IF NOT EXISTS principle_conflicts_principle2_uri_idx ON principle_conflicts (principle2_uri);
        """)

        logger.info("Created principle_conflicts table")

        # Create case_operationalization table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS case_operationalization (
                id SERIAL PRIMARY KEY,
                case_id INTEGER NOT NULL,
                technique_name TEXT NOT NULL,
                technique_matches JSONB,
                confidence FLOAT DEFAULT 0.0,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS case_operationalization_case_id_idx ON case_operationalization (case_id);
            CREATE INDEX IF NOT EXISTS case_operationalization_technique_name_idx ON case_operationalization (technique_name);
        """)

        logger.info("Created case_operationalization table")

        # Create case_triples table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS case_triples (
                id SERIAL PRIMARY KEY,
                case_id INTEGER NOT NULL,
                triples TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS case_triples_case_id_idx ON case_triples (case_id);
        """)

        logger.info("Created case_triples table")

        # Add triggers for updated_at timestamps
        cur.execute("""
            CREATE OR REPLACE FUNCTION update_modified_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = CURRENT_TIMESTAMP;
                RETURN NEW;
            END;
            $$ LANGUAGE 'plpgsql';

            DROP TRIGGER IF EXISTS update_principle_instantiations_timestamp ON principle_instantiations;
            CREATE TRIGGER update_principle_instantiations_timestamp
            BEFORE UPDATE ON principle_instantiations
            FOR EACH ROW EXECUTE PROCEDURE update_modified_column();

            DROP TRIGGER IF EXISTS update_principle_conflicts_timestamp ON principle_conflicts;
            CREATE TRIGGER update_principle_conflicts_timestamp
            BEFORE UPDATE ON principle_conflicts
            FOR EACH ROW EXECUTE PROCEDURE update_modified_column();

            DROP TRIGGER IF EXISTS update_case_operationalization_timestamp ON case_operationalization;
            CREATE TRIGGER update_case_operationalization_timestamp
            BEFORE UPDATE ON case_operationalization
            FOR EACH ROW EXECUTE PROCEDURE update_modified_column();

            DROP TRIGGER IF EXISTS update_case_triples_timestamp ON case_triples;
            CREATE TRIGGER update_case_triples_timestamp
            BEFORE UPDATE ON case_triples
            FOR EACH ROW EXECUTE PROCEDURE update_modified_column();
        """)

        logger.info("Added timestamp triggers")

        # Commit changes
        conn.commit()
        logger.info("Successfully created all tables for McLaren's extensional definition analysis")

        # Close the cursor and connection
        cur.close()
        conn.close()

        return True
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        traceback.print_exc()
        
        # Rollback changes
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
            
        return False

def drop_tables():
    """
    Drop the tables used for McLaren's extensional definition analysis.
    """
    try:
        # Connect to the database
        conn = psycopg2.connect(**DB_PARAMS)
        conn.autocommit = False
        cur = conn.cursor()
        
        # Drop tables
        cur.execute("""
            DROP TABLE IF EXISTS principle_instantiations CASCADE;
            DROP TABLE IF EXISTS principle_conflicts CASCADE;
            DROP TABLE IF EXISTS case_operationalization CASCADE;
            DROP TABLE IF EXISTS case_triples CASCADE;
        """)
        
        # Commit changes
        conn.commit()
        logger.info("Successfully dropped all tables for McLaren's extensional definition analysis")
        
        # Close the cursor and connection
        cur.close()
        conn.close()
        
        return True
    except Exception as e:
        logger.error(f"Error dropping tables: {str(e)}")
        traceback.print_exc()
        
        # Rollback changes
        if 'conn' in locals() and conn:
            conn.rollback()
            conn.close()
            
        return False

if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Create database tables for McLaren\'s extensional definition analysis.')
    parser.add_argument('--drop', action='store_true', help='Drop existing tables before creating new ones')
    args = parser.parse_args()
    
    if args.drop:
        logger.info("Dropping existing tables...")
        if drop_tables():
            logger.info("Successfully dropped existing tables")
        else:
            logger.error("Failed to drop existing tables")
            exit(1)
    
    logger.info("Creating tables...")
    if create_tables():
        logger.info("Successfully created tables")
    else:
        logger.error("Failed to create tables")
        exit(1)
    
    logger.info("Database migration completed successfully")
