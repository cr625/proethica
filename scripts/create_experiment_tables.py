#!/usr/bin/env python3
"""
Script to create the experiment tables for ProEthica.

This script creates the necessary database tables for the experiment:
- experiment_runs
- prediction_targets
- experiment_predictions
- experiment_evaluations
"""

import os
import sys
import logging
from datetime import datetime
from sqlalchemy import create_engine, MetaData
from sqlalchemy.exc import SQLAlchemyError

# Add the parent directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from app.models.experiment import ExperimentRun, PredictionTarget, Prediction, ExperimentEvaluation

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_experiment_tables():
    """Create all experiment-related tables."""
    try:
        # Set up environment variables
        os.environ['ENVIRONMENT'] = 'development'
        os.environ['DATABASE_URL'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
        os.environ['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
        
        # Create a custom app configuration
        class Config:
            SQLALCHEMY_DATABASE_URI = 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm'
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            SECRET_KEY = 'dev-key'
            DEBUG = True
        
        # Create app with custom config
        app = create_app()
        app.config.from_object(Config)
        
        with app.app_context():
            logger.info("Creating experiment tables...")
            
            # Create all tables defined in the experiment models
            # This will create only the tables that don't already exist
            db.create_all()
            
            logger.info("Tables created successfully")
            
            # Verify tables were created
            verify_tables()
            
    except Exception as e:
        logger.exception(f"Failed to create tables: {str(e)}")
        sys.exit(1)

def verify_tables():
    """Verify that the experiment tables were created correctly."""
    try:
        from sqlalchemy import inspect
        
        # Get the inspector
        inspector = inspect(db.engine)
        
        # Expected tables
        expected_tables = [
            'experiment_runs',
            'prediction_targets',
            'experiment_predictions',
            'experiment_evaluations'
        ]
        
        # Get all tables in the database
        existing_tables = inspector.get_table_names()
        
        logger.info(f"Total tables in database: {len(existing_tables)}")
        
        # Check each expected table
        for table in expected_tables:
            if table in existing_tables:
                logger.info(f"✓ Table '{table}' exists")
                
                # Get column info
                columns = inspector.get_columns(table)
                logger.info(f"  Columns: {', '.join([col['name'] for col in columns])}")
            else:
                logger.error(f"✗ Table '{table}' is missing")
                
    except Exception as e:
        logger.exception(f"Error verifying tables: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    logger.info("Starting ProEthica experiment tables creation")
    create_experiment_tables()
    logger.info("Script completed successfully")