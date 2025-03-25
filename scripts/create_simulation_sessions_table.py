#!/usr/bin/env python3
"""
Script to create the simulation_sessions table in the database.

This script creates a new table for storing simulation sessions, which include
the state and history of a simulation run, including all decisions made,
evaluations, and the timeline of events.

Usage:
    python scripts/create_simulation_sessions_table.py
"""

import os
import sys
import logging
from datetime import datetime

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('create_simulation_sessions_table')

def main():
    """Main function to create the simulation_sessions table."""
    try:
        from app import create_app, db
        from app.models.simulation_session import SimulationSession
    except ImportError as e:
        logger.error(f"Failed to import required modules: {e}")
        sys.exit(1)
    
    app = create_app()
    
    with app.app_context():
        # Check if the table already exists
        table_name = SimulationSession.__tablename__
        if table_name in db.metadata.tables:
            logger.info(f"Table '{table_name}' already exists.")
            return
        
        # Create the table
        logger.info(f"Creating table '{table_name}'...")
        
        # Create the table using SQLAlchemy's create_all method
        db.create_all(tables=[db.metadata.tables[table_name]])
        
        logger.info(f"Table '{table_name}' created successfully.")
        
        # Verify the table was created
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        if table_name in inspector.get_table_names():
            logger.info(f"Verified table '{table_name}' exists in the database.")
        else:
            logger.error(f"Failed to create table '{table_name}'.")
            sys.exit(1)

if __name__ == "__main__":
    main()
