#!/usr/bin/env python3
"""
Script to apply the ProEthica experiment tables migration.

This script creates the necessary database tables for the ProEthica experiment:
- experiment_runs
- experiment_predictions
- experiment_evaluations
"""

import os
import sys
import logging
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app import db, create_app

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_migration():
    """Run the experiment tables migration."""
    try:
        # Set up environment variables for database connection
        os.environ['ENVIRONMENT'] = 'codespace'
        os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
        os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
        
        # Apply SQLAlchemy URL fix if needed
        try:
            import patch_sqlalchemy_url
            # The main function in this script is patch_create_app
            patch_sqlalchemy_url.patch_create_app()
        except Exception as e:
            logger.warning(f"Failed to apply SQLAlchemy URL patch: {str(e)}")
        
        # Create app context with explicit configuration
        app = create_app()
        
        # Set database URI directly
        app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
        app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
        
        # Reinitialize the database with the new configuration
        db.init_app(app)
        with app.app_context():
            # Read the SQL file
            migration_path = os.path.join('migrations', 'sql', 'create_experiment_tables.sql')
            with open(migration_path, 'r') as file:
                sql = file.read()
                
            logger.info("Applying experiment tables migration...")
            
            # Split SQL into statements and execute each one
            statements = sql.split(';')
            for statement in statements:
                if statement.strip():
                    try:
                        db.session.execute(text(statement))
                        db.session.commit()
                    except SQLAlchemyError as e:
                        db.session.rollback()
                        logger.error(f"Error executing statement: {str(e)}")
                        logger.error(f"Statement: {statement}")
                        raise
            
            logger.info("Migration completed successfully")
            
            # Verify tables were created
            verify_tables()
            
    except Exception as e:
        logger.exception(f"Migration failed: {str(e)}")
        sys.exit(1)

def verify_tables():
    """Verify that the experiment tables were created correctly."""
    try:
        # Check each table
        tables = [
            'experiment_runs',
            'experiment_predictions',
            'experiment_evaluations'
        ]
        
        for table in tables:
            # Check if table exists
            result = db.session.execute(text(f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table}')"))
            exists = result.scalar()
            
            if exists:
                logger.info(f"Table '{table}' created successfully")
                
                # Count rows
                count_result = db.session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = count_result.scalar()
                logger.info(f"Table '{table}' contains {count} rows")
            else:
                logger.error(f"Table '{table}' was not created")
                sys.exit(1)
                
    except Exception as e:
        logger.exception(f"Error verifying tables: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    logger.info("Starting ProEthica experiment tables migration")
    run_migration()
    logger.info("Migration script completed")
