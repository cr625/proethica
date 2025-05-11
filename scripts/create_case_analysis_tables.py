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
    db_uri = os.getenv('DATABASE_URL')
    if not db_uri:
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = os.getenv('DB_PORT', '5433')  # Docker PostgreSQL runs on port 5433
        db_name = os.getenv('DB_NAME', 'proethica')
        db_user = os.getenv('DB_USER', 'postgres')
        db_pass = os.getenv('DB_PASSWORD', 'postgres')
        db_uri = f"postgresql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
    
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
    metadata = MetaData()
    
    # Create case_analysis table if it doesn't exist
    if not check_table_exists(conn, 'case_analysis'):
        logger.info("Creating case_analysis table...")
        case_analysis = Table(
            'case_analysis',
            metadata,
            Column('id', Integer, primary_key=True),
            Column('case_id', Integer, ForeignKey('cases.id'), nullable=False),
            Column('analysis_date', DateTime, default=datetime.datetime.utcnow),
            Column('analyzer_id', String(255), nullable=False),  # ID of the component that did the analysis
            Column('analyzer_version', String(50)),
            Column('analysis_complete', Boolean, default=False),
            Column('analysis_data', JSON),  # Stores the full analysis json data
            Column('analysis_summary', Text),
            Column('error_message', Text),
        )
    
    # Create case_entities table if it doesn't exist
    if not check_table_exists(conn, 'case_entities'):
        logger.info("Creating case_entities table...")
        case_entities = Table(
            'case_entities',
            metadata,
            Column('id', Integer, primary_key=True),
            Column('case_id', Integer, ForeignKey('cases.id'), nullable=False),
            Column('entity_id', String(255), nullable=False),  # IRI or ID of the ontology entity
            Column('entity_type', String(50), nullable=False),  # Type of entity (e.g., principle, action, role)
            Column('entity_label', String(255)),
            Column('relevance_score', Float),  # Score indicating relevance to the case
            Column('extraction_date', DateTime, default=datetime.datetime.utcnow),
            Column('extraction_method', String(50)),  # Method used to extract this entity
            Column('context', Text),  # Text context where this entity was found
            Column('entity_data', JSON),  # Additional entity data
        )
    
    # Create case_temporal_elements table if it doesn't exist
    if not check_table_exists(conn, 'case_temporal_elements'):
        logger.info("Creating case_temporal_elements table...")
        case_temporal_elements = Table(
            'case_temporal_elements',
            metadata,
            Column('id', Integer, primary_key=True),
            Column('case_id', Integer, ForeignKey('cases.id'), nullable=False),
            Column('element_type', String(50), nullable=False),  # Type of temporal element (event, action, etc.)
            Column('element_label', String(255)),
            Column('start_index', Integer),  # Position in the case text where this element starts
            Column('end_index', Integer),  # Position in the case text where this element ends
            Column('temporal_order', Integer),  # Order of this element in the temporal sequence
            Column('temporal_relation', String(50)),  # Relation to other elements (before, after, during, etc.)
            Column('related_element_id', Integer, ForeignKey('case_temporal_elements.id')),  # ID of related element
            Column('element_data', JSON),  # Additional temporal element data
        )
    
    # Create case_principles table if it doesn't exist
    if not check_table_exists(conn, 'case_principles'):
        logger.info("Creating case_principles table...")
        case_principles = Table(
            'case_principles',
            metadata,
            Column('id', Integer, primary_key=True),
            Column('case_id', Integer, ForeignKey('cases.id'), nullable=False),
            Column('principle_id', String(255), nullable=False),  # IRI or ID of the principle
            Column('principle_label', String(255)),
            Column('principle_text', Text),
            Column('relevance_score', Float),  # Score indicating relevance to the case
            Column('is_violated', Boolean),
            Column('is_satisfied', Boolean),
            Column('is_overridden', Boolean),
            Column('overridden_by', String(255)),  # ID of overriding principle if any
            Column('principle_data', JSON),  # Additional principle-specific data
        )
    
    # Create case_principle_instantiations table if it doesn't exist
    if not check_table_exists(conn, 'case_principle_instantiations'):
        logger.info("Creating case_principle_instantiations table...")
        case_principle_instantiations = Table(
            'case_principle_instantiations',
            metadata,
            Column('id', Integer, primary_key=True),
            Column('case_id', Integer, ForeignKey('cases.id'), nullable=False),
            Column('principle_id', String(255), nullable=False),  # IRI or ID of the principle
            Column('relevant_fact_ids', JSON),  # IDs of facts that make the principle relevant
            Column('violation_fact_ids', JSON),  # IDs of facts related to violation
            Column('instantiation_type', String(50)),  # Type of instantiation
            Column('instantiation_data', JSON),  # Additional instantiation data
        )
    
    # Create case_relationships table if it doesn't exist
    if not check_table_exists(conn, 'case_relationships'):
        logger.info("Creating case_relationships table...")
        case_relationships = Table(
            'case_relationships',
            metadata,
            Column('id', Integer, primary_key=True),
            Column('source_case_id', Integer, ForeignKey('cases.id'), nullable=False),
            Column('target_case_id', Integer, ForeignKey('cases.id'), nullable=False),
            Column('relation_type', String(50), nullable=False),  # Type of relationship (similar, precedent, etc.)
            Column('similarity_score', Float),  # Score indicating similarity between cases
            Column('common_entities', JSON),  # Entities common to both cases
            Column('common_principles', JSON),  # Principles common to both cases
            Column('relationship_data', JSON),  # Additional relationship data
        )
    
    # Create the tables if they don't exist
    metadata.create_all(engine)
    logger.info("Case analysis tables created successfully")
    
    return True

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
