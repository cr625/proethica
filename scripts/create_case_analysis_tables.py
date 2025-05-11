#!/usr/bin/env python3
"""
Case Analysis Database Schema Migration Script

This script extends the ProEthica database schema to support ontology-based case analysis.
It adds tables for:
- Case analysis results
- Ontology entity extraction tracking
- Temporal representation of cases
- Relationships between cases based on ontology elements

Usage:
    python create_case_analysis_tables.py
"""

import os
import sys
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData, Table, Column, String, Integer, \
                       Text, Boolean, DateTime, ForeignKey, Float, JSON
from sqlalchemy.exc import ProgrammingError, OperationalError
from sqlalchemy.sql import text
import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('Case-Analysis-Schema')

# Load environment variables
load_dotenv()

def get_database_uri():
    """Get the database URI from environment variables"""
    # Instead of relying on the escaped DATABASE_URL, let's build it manually
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5433')  # Docker PostgreSQL runs on port 5433
    db_name = os.getenv('DB_NAME', 'ai_ethical_dm')  # Match the database name from .env
    db_user = os.getenv('DB_USER', 'postgres')
    db_pass = 'PASS'  # Use the same password as in the .env file
    
    db_uri = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    
    logger.info(f"Using database URI: {db_uri}")
    return db_uri

def create_connection():
    """Create a database connection"""
    db_uri = get_database_uri()
    
    try:
        engine = create_engine(db_uri)
        conn = engine.connect()
        logger.info("Connected to database successfully")
        return conn, engine
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        sys.exit(1)

def check_table_exists(conn, table_name):
    """Check if a table exists in the database"""
    try:
        result = conn.execute(text(f"SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}')"))
        return result.scalar()
    except Exception as e:
        logger.error(f"Error checking if table {table_name} exists: {e}")
        return False

def create_case_analysis_tables(conn, engine):
    """Create tables for case analysis"""
    try:
        # Use raw SQL to create tables with exact control over schema
        
        # Create case_analysis table if it doesn't exist
        if not check_table_exists(conn, 'case_analysis'):
            logger.info("Creating case_analysis table...")
            conn.execute(text("""
                CREATE TABLE case_analysis (
                    id SERIAL PRIMARY KEY,
                    case_id INTEGER NOT NULL REFERENCES scenarios(id),
                    analysis_date TIMESTAMP DEFAULT NOW(),
                    analyzer_id VARCHAR(255) NOT NULL,
                    analyzer_version VARCHAR(50),
                    analysis_complete BOOLEAN DEFAULT FALSE,
                    analysis_data JSONB,
                    analysis_summary TEXT,
                    error_message TEXT
                )
            """))
        
        # Create case_entities table if it doesn't exist
        if not check_table_exists(conn, 'case_entities'):
            logger.info("Creating case_entities table...")
            conn.execute(text("""
                CREATE TABLE case_entities (
                    id SERIAL PRIMARY KEY,
                    case_id INTEGER NOT NULL REFERENCES scenarios(id),
                    entity_id VARCHAR(255) NOT NULL,
                    entity_type VARCHAR(50) NOT NULL,
                    entity_label VARCHAR(255),
                    relevance_score FLOAT,
                    extraction_date TIMESTAMP DEFAULT NOW(),
                    extraction_method VARCHAR(50),
                    context TEXT,
                    entity_data JSONB
                )
            """))
        
        # Create case_temporal_elements table if it doesn't exist
        if not check_table_exists(conn, 'case_temporal_elements'):
            logger.info("Creating case_temporal_elements table...")
            conn.execute(text("""
                CREATE TABLE case_temporal_elements (
                    id SERIAL PRIMARY KEY,
                    case_id INTEGER NOT NULL REFERENCES scenarios(id),
                    element_type VARCHAR(50) NOT NULL,
                    element_label VARCHAR(255),
                    start_index INTEGER,
                    end_index INTEGER,
                    temporal_order INTEGER,
                    temporal_relation VARCHAR(50),
                    related_element_id INTEGER,
                    element_data JSONB
                )
            """))
            
            # Add the self-reference after the table is created
            conn.execute(text("""
                ALTER TABLE case_temporal_elements 
                ADD CONSTRAINT case_temporal_elements_related_element_id_fkey 
                FOREIGN KEY (related_element_id) REFERENCES case_temporal_elements(id)
            """))
        
        # Create case_principles table if it doesn't exist
        if not check_table_exists(conn, 'case_principles'):
            logger.info("Creating case_principles table...")
            conn.execute(text("""
                CREATE TABLE case_principles (
                    id SERIAL PRIMARY KEY,
                    case_id INTEGER NOT NULL REFERENCES scenarios(id),
                    principle_id VARCHAR(255) NOT NULL,
                    principle_label VARCHAR(255),
                    principle_text TEXT,
                    relevance_score FLOAT,
                    is_violated BOOLEAN,
                    is_satisfied BOOLEAN,
                    is_overridden BOOLEAN,
                    overridden_by VARCHAR(255),
                    principle_data JSONB
                )
            """))
        
        # Create case_principle_instantiations table if it doesn't exist
        if not check_table_exists(conn, 'case_principle_instantiations'):
            logger.info("Creating case_principle_instantiations table...")
            conn.execute(text("""
                CREATE TABLE case_principle_instantiations (
                    id SERIAL PRIMARY KEY,
                    case_id INTEGER NOT NULL REFERENCES scenarios(id),
                    principle_id VARCHAR(255) NOT NULL,
                    relevant_fact_ids JSONB,
                    violation_fact_ids JSONB,
                    instantiation_type VARCHAR(50),
                    instantiation_data JSONB
                )
            """))
        
        # Create case_relationships table if it doesn't exist
        if not check_table_exists(conn, 'case_relationships'):
            logger.info("Creating case_relationships table...")
            conn.execute(text("""
                CREATE TABLE case_relationships (
                    id SERIAL PRIMARY KEY,
                    source_case_id INTEGER NOT NULL REFERENCES scenarios(id),
                    target_case_id INTEGER NOT NULL REFERENCES scenarios(id),
                    relation_type VARCHAR(50) NOT NULL,
                    similarity_score FLOAT,
                    common_entities JSONB,
                    common_principles JSONB,
                    relationship_data JSONB
                )
            """))
            
        logger.info("Case analysis tables created successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        return False

def create_indexes(conn):
    """Create indexes for performance optimization"""
    try:
        logger.info("Creating indexes...")
        
        # Add index on case_id for faster lookups
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_analysis_case_id ON case_analysis (case_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_entities_case_id ON case_entities (case_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_entities_entity_id ON case_entities (entity_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_entities_entity_type ON case_entities (entity_type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_temporal_elements_case_id ON case_temporal_elements (case_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_principles_case_id ON case_principles (case_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_principles_principle_id ON case_principles (principle_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_relationships_source_case_id ON case_relationships (source_case_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_case_relationships_target_case_id ON case_relationships (target_case_id)"))
        
        logger.info("Indexes created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating indexes: {e}")
        return False

def main():
    """Main function"""
    try:
        logger.info("Starting case analysis database schema migration...")
        
        # Create a connection to the database
        conn, engine = create_connection()
        
        # Create tables
        if not create_case_analysis_tables(conn, engine):
            logger.error("Failed to create case analysis tables")
            sys.exit(1)
        
        # Create indexes
        if not create_indexes(conn):
            logger.error("Failed to create indexes")
            sys.exit(1)
        
        logger.info("Database schema migration completed successfully")
        conn.close()
        
    except Exception as e:
        logger.error(f"Error during database schema migration: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
