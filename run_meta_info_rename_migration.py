#!/usr/bin/env python3
"""
Migration script to rename database columns to meta_info.

This script executes the SQL migration to rename meta_data/metadata columns to meta_info
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
    """Run the SQL migration to rename columns to meta_info."""
    logger.info("Running column rename migration to meta_info")
    
    try:
        # Read the SQL migration file
        migration_file = 'migrations/sql/rename_meta_data_to_meta_info.sql'
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
        # Check column names in experiment_predictions table
        conn = db.engine.connect()
        
        # Check experiment_predictions table
        result = conn.execute(db.text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'experiment_predictions'
            AND column_name IN ('meta_data', 'metadata', 'meta_info')
        """))
        
        prediction_columns = [row[0] for row in result]
        
        if 'meta_info' in prediction_columns:
            logger.info("Verified: experiment_predictions table has meta_info column")
        else:
            logger.error(f"Verification issue: experiment_predictions columns - unexpected state: {prediction_columns}")
            
        if 'meta_data' in prediction_columns or 'metadata' in prediction_columns:
            logger.error(f"Verification issue: experiment_predictions still has old column names: {prediction_columns}")
        
        # Check experiment_evaluations table
        result = conn.execute(db.text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'experiment_evaluations'
            AND column_name IN ('meta_data', 'metadata', 'meta_info')
        """))
        
        evaluation_columns = [row[0] for row in result]
        
        if 'meta_info' in evaluation_columns:
            logger.info("Verified: experiment_evaluations table has meta_info column")
        else:
            logger.error(f"Verification issue: experiment_evaluations columns - unexpected state: {evaluation_columns}")
            
        if 'meta_data' in evaluation_columns or 'metadata' in evaluation_columns:
            logger.error(f"Verification issue: experiment_evaluations still has old column names: {evaluation_columns}")
            
        return ('meta_info' in prediction_columns and 'meta_info' in evaluation_columns and
                'meta_data' not in prediction_columns and 'metadata' not in prediction_columns and
                'meta_data' not in evaluation_columns and 'metadata' not in evaluation_columns)
            
    except Exception as e:
        logger.exception(f"Error verifying migration: {str(e)}")
        return False

def main():
    """Main entry point for the migration script."""
    logger.info("Starting rename migration to meta_info")
    
    # Setup environment
    _, db = setup_environment()
    
    # Run migration
    run_migration(db)
    
    # Verify migration
    success = verify_migration(db)
    
    if success:
        logger.info("Migration to meta_info completed successfully")
        print("Migration completed successfully!")
    else:
        logger.error("Migration verification failed")
        print("Migration completed but verification failed. Check logs for details.")
        sys.exit(1)

if __name__ == '__main__':
    main()
