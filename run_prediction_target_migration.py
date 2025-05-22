#!/usr/bin/env python3
"""
Script to run the database migration for adding prediction target support.

This adds the target column to experiment_predictions table and creates the 
prediction_targets table to support enhanced prediction functionality.
"""

import os
import sys
import logging
import argparse
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def run_migration(host='localhost', port=5433, user='postgres', password='PASS', database='ai_ethical_dm'):
    """
    Run the SQL migration script for adding prediction target support.
    
    Args:
        host: Database host
        port: Database port
        user: Database user
        password: Database password
        database: Database name
    """
    try:
        # Import after environment setup
        import psycopg2
        
        # Connect to the database
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            database=database
        )
        
        # Set autocommit to True for DDL operations
        conn.autocommit = True
        
        # Create a cursor
        cursor = conn.cursor()
        
        # Read the migration SQL
        migration_file = os.path.join('migrations', 'sql', 'add_prediction_target.sql')
        
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        # Execute the migration
        logger.info(f"Executing migration from {migration_file}")
        
        cursor.execute(migration_sql)
        
        # Close the cursor and connection
        cursor.close()
        conn.close()
        
        logger.info("Migration completed successfully")
        
    except Exception as e:
        logger.exception(f"Error running migration: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description='Run prediction target database migration')
    parser.add_argument('--host', type=str, default='localhost', help='Database host')
    parser.add_argument('--port', type=int, default=5433, help='Database port')
    parser.add_argument('--user', type=str, default='postgres', help='Database user')
    parser.add_argument('--password', type=str, default='PASS', help='Database password')
    parser.add_argument('--database', type=str, default='ai_ethical_dm', help='Database name')
    args = parser.parse_args()

    # Set up environment variables
    os.environ['ENVIRONMENT'] = 'codespace'
    os.environ['DATABASE_URL'] = f'postgresql://{args.user}:{args.password}@{args.host}:{args.port}/{args.database}'
    os.environ['SQLALCHEMY_DATABASE_URI'] = f'postgresql://{args.user}:{args.password}@{args.host}:{args.port}/{args.database}'
    
    # Load environment variables from .env file if it exists
    if os.path.exists('.env'):
        load_dotenv()
        logger.info("Loaded environment variables from .env file")
    
    # Run the migration
    run_migration(
        host=args.host,
        port=args.port,
        user=args.user,
        password=args.password,
        database=args.database
    )
