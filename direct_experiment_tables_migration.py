#!/usr/bin/env python3
"""
Direct migration script for ProEthica experiment tables.

This script directly connects to the database using SQLAlchemy and executes
the SQL migration statements, without relying on the Flask application context.
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Database connection settings
DB_HOST = 'localhost'
DB_PORT = '5433'
DB_USER = 'postgres'
DB_PASS = 'PASS'
DB_NAME = 'ai_ethical_dm'

def run_migration():
    """Run the experiment tables migration directly with SQLAlchemy."""
    try:
        # Create SQLAlchemy engine
        db_uri = f'postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
        logger.info(f"Connecting to database with URI: {db_uri}")
        
        engine = create_engine(db_uri)
        
        # Test connection
        try:
            connection = engine.connect()
            logger.info("Database connection successful")
            connection.close()
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            sys.exit(1)
        
        # Read the SQL file
        migration_path = os.path.join('migrations', 'sql', 'create_experiment_tables.sql')
        with open(migration_path, 'r') as file:
            sql = file.read()
            
        logger.info("Applying experiment tables migration...")
        
        # Execute SQL statements
        with engine.begin() as conn:
            # Split SQL into statements and execute each one
            statements = sql.split(';')
            for statement in statements:
                if statement.strip():
                    try:
                        conn.execute(text(statement))
                        logger.info("Statement executed successfully")
                    except SQLAlchemyError as e:
                        logger.error(f"Error executing statement: {str(e)}")
                        logger.error(f"Statement: {statement}")
                        raise
        
        logger.info("Migration completed successfully")
        
        # Verify tables were created
        verify_tables(engine)
            
    except Exception as e:
        logger.exception(f"Migration failed: {str(e)}")
        sys.exit(1)

def verify_tables(engine):
    """Verify that the experiment tables were created correctly."""
    try:
        # Check each table
        tables = [
            'experiment_runs',
            'experiment_predictions',
            'experiment_evaluations'
        ]
        
        with engine.connect() as conn:
            for table in tables:
                # Check if table exists
                result = conn.execute(text(
                    f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}')"
                ))
                exists = result.scalar()
                
                if exists:
                    logger.info(f"Table '{table}' created successfully")
                    
                    # Count rows
                    count_result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                    count = count_result.scalar()
                    logger.info(f"Table '{table}' contains {count} rows")
                else:
                    logger.error(f"Table '{table}' was not created")
                    sys.exit(1)
                
    except Exception as e:
        logger.exception(f"Error verifying tables: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    logger.info("Starting direct ProEthica experiment tables migration")
    run_migration()
    logger.info("Migration script completed")
