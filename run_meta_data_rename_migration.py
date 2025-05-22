#!/usr/bin/env python3
"""
Migration script to rename meta_data columns to metadata.

This script executes the SQL migration to rename the meta_data column to metadata
in experiment tables to ensure compatibility between SQLAlchemy models and database.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)

def setup_environment():
    """Set up the Flask application environment."""
    logger.info("Setting up environment")
    
    # Set up environment variables
    os.environ['ENVIRONMENT'] = 'codespace'
    os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
    os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
    
    # Load environment variables from .env file if it exists
    if os.path.exists('.env'):
        load_dotenv()
        logger.info("Loaded environment variables from .env file")
    
    # Apply SQLAlchemy URL fix if available
    try:
        import patch_sqlalchemy_url
        patch_sqlalchemy_url.patch_create_app()
        logger.info("Applied SQLAlchemy URL patch")
    except Exception as e:
        logger.warning(f"Failed to apply SQLAlchemy URL patch: {str(e)}")
    
    # Import after environment variables are set
    try:
        from app import create_app, db
        
        # Create and configure the app
        app = create_app('config')
        app.app_context().push()
        
        logger.info("App context set up successfully")
        return app, db
    except ImportError as e:
        logger.error(f"Failed to import required modules: {str(e)}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Error setting up Flask environment: {str(e)}")
        sys.exit(1)

def run_migration(db):
    """Run the SQL migration to rename meta_data columns."""
    logger.info("Running meta_data to metadata column rename migration")
    
    try:
        # Read the SQL migration file
        migration_file = 'migrations/sql/rename_meta_data_to_metadata.sql'
        with open(migration_file, 'r') as f:
            sql = f.read()
        
        # Execute the SQL migration
        conn = db.engine.connect()
        logger.info("Connected to database")
        
        # Execute each statement in the migration
        logger.info("Executing migration SQL")
        conn.execute(db.text(sql))
        conn.commit()
        logger.info("Migration completed successfully")
        
    except Exception as e:
        logger.exception(f"Error running migration: {str(e)}")
        sys.exit(1)

def verify_migration(db):
    """Verify that the migration was successful."""
    logger.info("Verifying migration results")
    
    try:
        # Check if the metadata columns exist and meta_data columns don't
        conn = db.engine.connect()
        
        # Check experiment_predictions table
        result = conn.execute(db.text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'experiment_predictions'
            AND column_name IN ('meta_data', 'metadata')
        """))
        
        columns = [row[0] for row in result]
        
        if 'metadata' in columns and 'meta_data' not in columns:
            logger.info("Verified: experiment_predictions table has metadata column")
        else:
            logger.warning(f"Verification issue: experiment_predictions columns: {columns}")
        
        # Check experiment_evaluations table
        result = conn.execute(db.text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'experiment_evaluations'
            AND column_name IN ('meta_data', 'metadata')
        """))
        
        columns = [row[0] for row in result]
        
        if 'metadata' in columns and 'meta_data' not in columns:
            logger.info("Verified: experiment_evaluations table has metadata column")
        else:
            logger.warning(f"Verification issue: experiment_evaluations columns: {columns}")
            
    except Exception as e:
        logger.exception(f"Error verifying migration: {str(e)}")

def main():
    """Main entry point for the migration script."""
    logger.info("Starting meta_data to metadata column rename migration")
    
    # Setup environment
    _, db = setup_environment()
    
    # Run migration
    run_migration(db)
    
    # Verify migration
    verify_migration(db)
    
    logger.info("Migration process completed")
    print("Migration completed successfully!")

if __name__ == '__main__':
    main()
