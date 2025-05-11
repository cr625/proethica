#!/usr/bin/env python3
"""
Database migration script to create tables needed for storing McLaren's
extensional definition analysis results.

This script creates the following tables:
1. principle_instantiations - Links principles to specific facts in cases
2. principle_conflicts - Records conflicts between principles in cases
3. case_operationalization - Tracks which operationalization techniques were used in cases
4. case_triples - Stores RDF triples generated from the analysis

Usage:
    python scripts/database_migrations/create_extensional_definition_tables.py
"""

import sys
import os
import logging
from datetime import datetime
import traceback

# Add the parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app import create_app, db
from sqlalchemy import text

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("create_extensional_definition_tables")


def create_tables():
    """
    Create the tables needed for McLaren's extensional definition analysis.
    """
    try:
        # Create principle_instantiations table
        db.session.execute(text("""
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
        """))
        
        logger.info("Created principle_instantiations table")
        
        # Create principle_conflicts table
        db.session.execute(text("""
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
        """))
        
        logger.info("Created principle_conflicts table")
        
        # Create case_operationalization table
        db.session.execute(text("""
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
        """))
        
        logger.info("Created case_operationalization table")
        
        # Create case_triples table
        db.session.execute(text("""
            CREATE TABLE IF NOT EXISTS case_triples (
                id SERIAL PRIMARY KEY,
                case_id INTEGER NOT NULL,
                triples TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS case_triples_case_id_idx ON case_triples (case_id);
        """))
        
        logger.info("Created case_triples table")
        
        # Add foreign key constraints if Document table exists
        # Check if document table exists
        result = db.session.execute(text("SELECT to_regclass('public.document')")).fetchone()
        
        if result[0]:
            db.session.execute(text("""
                ALTER TABLE principle_instantiations 
                ADD CONSTRAINT fk_principle_instantiations_case_id 
                FOREIGN KEY (case_id) REFERENCES document (id) 
                ON DELETE CASCADE;
                
                ALTER TABLE principle_conflicts 
                ADD CONSTRAINT fk_principle_conflicts_case_id 
                FOREIGN KEY (case_id) REFERENCES document (id) 
                ON DELETE CASCADE;
                
                ALTER TABLE case_operationalization 
                ADD CONSTRAINT fk_case_operationalization_case_id 
                FOREIGN KEY (case_id) REFERENCES document (id) 
                ON DELETE CASCADE;
                
                ALTER TABLE case_triples 
                ADD CONSTRAINT fk_case_triples_case_id 
                FOREIGN KEY (case_id) REFERENCES document (id) 
                ON DELETE CASCADE;
            """))
            
            logger.info("Added foreign key constraints")
        else:
            logger.warning("Document table not found. Foreign key constraints not added.")
        
        # Add triggers for updated_at timestamps
        db.session.execute(text("""
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
        """))
        
        logger.info("Added timestamp triggers")
        
        # Commit changes
        db.session.commit()
        logger.info("Successfully created all tables for McLaren's extensional definition analysis")
        
        return True
    except Exception as e:
        logger.error(f"Error creating tables: {str(e)}")
        traceback.print_exc()
        db.session.rollback()
        return False


def drop_tables():
    """
    Drop the tables used for McLaren's extensional definition analysis.
    """
    try:
        db.session.execute(text("DROP TABLE IF EXISTS principle_instantiations CASCADE;"))
        db.session.execute(text("DROP TABLE IF EXISTS principle_conflicts CASCADE;"))
        db.session.execute(text("DROP TABLE IF EXISTS case_operationalization CASCADE;"))
        db.session.execute(text("DROP TABLE IF EXISTS case_triples CASCADE;"))
        db.session.commit()
        logger.info("Successfully dropped all tables for McLaren's extensional definition analysis")
        return True
    except Exception as e:
        logger.error(f"Error dropping tables: {str(e)}")
        traceback.print_exc()
        db.session.rollback()
        return False


def main():
    """Main entry point for script."""
    parser = argparse.ArgumentParser(description='Create database tables for McLaren\'s extensional definition analysis.')
    parser.add_argument('--drop', action='store_true', help='Drop existing tables before creating new ones')
    args = parser.parse_args()
    
    app = create_app()
    with app.app_context():
        if args.drop:
            logger.info("Dropping existing tables...")
            if drop_tables():
                logger.info("Successfully dropped existing tables")
            else:
                logger.error("Failed to drop existing tables")
                return
        
        logger.info("Creating tables...")
        if create_tables():
            logger.info("Successfully created tables")
        else:
            logger.error("Failed to create tables")
            return


if __name__ == '__main__':
    import argparse
    main()
