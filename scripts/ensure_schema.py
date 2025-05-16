#!/usr/bin/env python3
"""
Ensure database schema has all required columns for guideline concept extraction.
This script automatically adds missing columns to the entity_triples table and other
related tables to support the guideline concept flow.
"""

import os
import sys
import logging
import argparse
from sqlalchemy import create_engine, Column, Integer, String, Boolean, Text, Float, DateTime, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import inspect
from sqlalchemy.schema import CreateTable

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Define base
Base = declarative_base()

def get_db_url():
    """Get database URL from environment or use default."""
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        # Default for local development
        db_url = "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
        logger.info(f"No DATABASE_URL found, using default: {db_url}")
    return db_url

class Guidelines(Base):
    """Guidelines table model."""
    __tablename__ = 'guidelines'
    
    id = Column(Integer, primary_key=True)
    world_id = Column(Integer, nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text)
    source_url = Column(String(1024))
    file_path = Column(String(1024))
    file_type = Column(String(50))
    # Use proper SQL definition for FLOAT[] array type
    embedding = Column("embedding", Text)  # Represented as Text in SQLAlchemy, but FLOAT[] in PostgreSQL
    guideline_metadata = Column(JSONB, default={})
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

class EntityTriple(Base):
    """Entity triple table model with all required columns."""
    __tablename__ = 'entity_triples'
    
    id = Column(Integer, primary_key=True)
    subject = Column(String(255), nullable=False)
    predicate = Column(String(255), nullable=False)
    object_literal = Column(Text)
    object_uri = Column(String(255))
    is_literal = Column(Boolean, nullable=False)
    graph = Column(String(255))
    
    # Additional fields for label display
    subject_label = Column(String(255))
    predicate_label = Column(String(255))
    object_label = Column(String(255))
    
    # Metadata and timestamps
    triple_metadata = Column(JSONB, default={})
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    
    # Enhanced temporal fields
    temporal_confidence = Column(Float, default=1.0)
    temporal_context = Column(JSONB, default={})
    
    # Entity references
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    
    # Foreign keys
    world_id = Column(Integer, nullable=True)
    guideline_id = Column(Integer, nullable=True)
    scenario_id = Column(Integer, nullable=True)
    character_id = Column(Integer, nullable=True)

def ensure_entity_triples_columns(engine, add_missing=True):
    """
    Check if entity_triples table has all required columns 
    and add any that are missing.
    """
    inspector = inspect(engine)
    
    # Check if the entity_triples table exists
    if 'entity_triples' not in inspector.get_table_names():
        logger.warning("entity_triples table doesn't exist")
        
        if add_missing:
            logger.info("Creating entity_triples table")
            EntityTriple.__table__.create(engine)
            return True
        return False
    
    # Get existing columns
    existing_columns = {col['name'] for col in inspector.get_columns('entity_triples')}
    logger.info(f"Found {len(existing_columns)} columns in entity_triples table")
    
    # Define required columns with their types
    required_columns = {
        'id': Column(Integer, primary_key=True),
        'subject': Column(String(255), nullable=False),
        'predicate': Column(String(255), nullable=False),
        'object_literal': Column(Text),
        'object_uri': Column(String(255)),
        'is_literal': Column(Boolean, nullable=False),
        'subject_label': Column(String(255)),
        'predicate_label': Column(String(255)),
        'object_label': Column(String(255)),
        'entity_type': Column(String(50), nullable=False),
        'entity_id': Column(Integer, nullable=False),
        'world_id': Column(Integer, nullable=True),
        'guideline_id': Column(Integer, nullable=True),
        'temporal_confidence': Column(Float, default=1.0),
        'temporal_context': Column(JSONB, default={})
    }
    
    # Check which required columns are missing
    missing_columns = {col_name: col_def for col_name, col_def in required_columns.items()
                      if col_name not in existing_columns}
    
    if not missing_columns:
        logger.info("All required columns exist in entity_triples table")
        return True
    
    logger.warning(f"Missing {len(missing_columns)} columns in entity_triples: {', '.join(missing_columns.keys())}")
    
    if not add_missing:
        return False
    
    # Add missing columns
    connection = engine.connect()
    for col_name, column in missing_columns.items():
        col_type = column.type.compile(dialect=engine.dialect)
        nullable = "NULL" if column.nullable else "NOT NULL"
        default = f"DEFAULT {column.default.arg}" if column.default is not None else ""
        
        try:
            logger.info(f"Adding column {col_name} ({col_type} {nullable} {default}) to entity_triples")
            sql = text(f"ALTER TABLE entity_triples ADD COLUMN IF NOT EXISTS {col_name} {col_type} {nullable} {default};")
            connection.execute(sql)
        except Exception as e:
            logger.error(f"Error adding column {col_name}: {str(e)}")
    
    connection.close()
    
    # Verify all columns added
    inspector = inspect(engine)
    updated_columns = {col['name'] for col in inspector.get_columns('entity_triples')}
    still_missing = {col for col in missing_columns.keys() if col not in updated_columns}
    
    if still_missing:
        logger.warning(f"Some columns could not be added: {', '.join(still_missing)}")
        return False
    else:
        logger.info("Successfully added all missing columns to entity_triples table")
        return True

def ensure_guidelines_table(engine, add_missing=True):
    """Ensure the guidelines table exists."""
    inspector = inspect(engine)
    
    # Check if the guidelines table exists
    if 'guidelines' not in inspector.get_table_names():
        logger.warning("guidelines table doesn't exist")
        
        if add_missing:
            logger.info("Creating guidelines table")
            Guidelines.__table__.create(engine)
            return True
        return False
    
    # Get existing columns
    existing_columns = {col['name'] for col in inspector.get_columns('guidelines')}
    logger.info(f"Found {len(existing_columns)} columns in guidelines table")
    
    # Define required columns with their types
    required_columns = {
        'id': Column(Integer, primary_key=True),
        'world_id': Column(Integer, nullable=False),
        'title': Column(String(255), nullable=False),
        'content': Column(Text),
        'source_url': Column(String(1024)),
        'file_path': Column(String(1024)),
        'file_type': Column(String(50)),
        'embedding': Column("embedding", Text),  # Represented as Text in SQLAlchemy, but FLOAT[] in PostgreSQL
        'guideline_metadata': Column(JSONB, default={})
    }
    
    # Check which required columns are missing
    missing_columns = {col_name: col_def for col_name, col_def in required_columns.items()
                      if col_name not in existing_columns}
    
    if not missing_columns:
        logger.info("All required columns exist in guidelines table")
        return True
    
    logger.warning(f"Missing {len(missing_columns)} columns in guidelines: {', '.join(missing_columns.keys())}")
    
    if not add_missing:
        return False
    
    # Add missing columns
    connection = engine.connect()
    for col_name, column in missing_columns.items():
        col_type = column.type.compile(dialect=engine.dialect)
        nullable = "NULL" if column.nullable else "NOT NULL"
        default = f"DEFAULT {column.default.arg}" if column.default is not None else ""
        
        try:
            logger.info(f"Adding column {col_name} ({col_type} {nullable} {default}) to guidelines")
            sql = text(f"ALTER TABLE guidelines ADD COLUMN IF NOT EXISTS {col_name} {col_type} {nullable} {default};")
            connection.execute(sql)
        except Exception as e:
            logger.error(f"Error adding column {col_name}: {str(e)}")
    
    connection.close()
    return True

def add_foreign_key_constraints(engine):
    """Add missing foreign key constraints."""
    try:
        connection = engine.connect()
        
        # Check if world_id is properly constrained
        # Note: This will only work if both tables and columns exist
        sql = text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = 'entity_triples' 
                AND ccu.table_name = 'worlds'
                AND ccu.column_name = 'id'
                AND tc.table_schema = 'public'
            ) THEN
                BEGIN
                    ALTER TABLE entity_triples 
                    ADD CONSTRAINT fk_entity_triples_world_id 
                    FOREIGN KEY (world_id) REFERENCES worlds(id) ON DELETE CASCADE;
                    RAISE NOTICE 'Added foreign key constraint for world_id';
                EXCEPTION
                    WHEN others THEN
                        RAISE NOTICE 'Could not add foreign key constraint for world_id: %', SQLERRM;
                END;
            END IF;
        END $$;
        """)
        connection.execute(sql)
        
        # Check if guideline_id is properly constrained
        sql_guideline = text("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.table_constraints tc
                JOIN information_schema.constraint_column_usage ccu ON tc.constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = 'entity_triples' 
                AND ccu.table_name = 'guidelines'
                AND ccu.column_name = 'id'
                AND tc.table_schema = 'public'
            ) THEN
                BEGIN
                    ALTER TABLE entity_triples 
                    ADD CONSTRAINT fk_entity_triples_guideline_id 
                    FOREIGN KEY (guideline_id) REFERENCES guidelines(id) ON DELETE CASCADE;
                    RAISE NOTICE 'Added foreign key constraint for guideline_id';
                EXCEPTION
                    WHEN others THEN
                        RAISE NOTICE 'Could not add foreign key constraint for guideline_id: %', SQLERRM;
                END;
            END IF;
        END $$;
        """)
        connection.execute(sql_guideline)
        
        connection.close()
        return True
    except Exception as e:
        logger.error(f"Error adding foreign key constraints: {str(e)}")
        return False

def ensure_schema(add_missing=True):
    """Ensure the database has all required tables and columns."""
    try:
        engine = create_engine(get_db_url())
        
        # Check/create the entity_triples table with all columns
        entity_triples_ok = ensure_entity_triples_columns(engine, add_missing)
        
        # Check/create the guidelines table
        guidelines_ok = ensure_guidelines_table(engine, add_missing)
        
        # Add foreign key constraints
        if add_missing and entity_triples_ok and guidelines_ok:
            add_foreign_key_constraints(engine)
        
        # Report status
        if entity_triples_ok and guidelines_ok:
            logger.info("Database schema verified and updated successfully")
            return True
        else:
            logger.warning("Schema verification completed with issues")
            return False
        
    except Exception as e:
        logger.exception(f"Error ensuring schema: {str(e)}")
        return False

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Ensure database schema for guideline concepts")
    parser.add_argument('--check-only', action='store_true', help="Check schema without making changes")
    args = parser.parse_args()
    
    logger.info("Checking database schema for concept extraction...")
    if ensure_schema(not args.check_only):
        logger.info("Schema verification completed successfully")
        sys.exit(0)
    else:
        logger.error("Schema verification found issues")
        sys.exit(1)

if __name__ == '__main__':
    main()
