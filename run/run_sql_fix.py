#!/usr/bin/env python3
"""
Execute the fix_embedding_column.sql script to fix the embedding column
in the guidelines table.
"""

import os
import sys
import logging
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

# Configure logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_db_url():
    """Get database URL from environment or use default."""
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        # Default for local development
        db_url = "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
        logger.info(f"No DATABASE_URL found, using default: {db_url}")
    return db_url

def parse_db_url(url):
    """Parse database URL into connection parameters."""
    # Format: postgresql://user:password@host:port/dbname
    url = url.replace('postgresql://', '')
    
    # Extract credentials and location
    credentials, location = url.split('@')
    
    # Extract username and password
    if ':' in credentials:
        username, password = credentials.split(':', 1)
    else:
        username = credentials
        password = ''
    
    # Extract host, port, and dbname
    if '/' in location:
        hostport, dbname = location.split('/', 1)
    else:
        hostport = location
        dbname = ''
    
    # Extract host and port
    if ':' in hostport:
        host, port = hostport.split(':')
        port = int(port)
    else:
        host = hostport
        port = 5432  # Default PostgreSQL port
    
    return {
        'user': username,
        'password': password,
        'host': host,
        'port': port,
        'dbname': dbname
    }

def execute_sql_file(db_params, sql_file):
    """Execute SQL commands from a file."""
    
    conn = None
    try:
        # Connect to the database
        logger.info(f"Connecting to database: {db_params['host']}:{db_params['port']}/{db_params['dbname']}")
        conn = psycopg2.connect(**db_params)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        
        # Create a cursor
        cursor = conn.cursor()
        
        # Read and execute SQL file
        logger.info(f"Executing SQL from file: {sql_file}")
        with open(sql_file, 'r') as f:
            sql_content = f.read()
            cursor.execute(sql_content)
        
        # Close cursor
        cursor.close()
        
        logger.info("SQL execution completed successfully")
        return True
    
    except Exception as e:
        logger.error(f"Error executing SQL: {str(e)}")
        return False
    
    finally:
        # Close connection
        if conn is not None:
            conn.close()

def main():
    """Main function to execute SQL fix."""
    
    # Define the SQL file path
    sql_file = 'fix_embedding_column.sql'
    
    # Check if the SQL file exists
    if not os.path.exists(sql_file):
        logger.error(f"SQL file not found: {sql_file}")
        sys.exit(1)
    
    # Get the database URL and parse it
    db_url = get_db_url()
    db_params = parse_db_url(db_url)
    
    # Execute the SQL file
    if execute_sql_file(db_params, sql_file):
        logger.info("Database fix completed successfully!")
        sys.exit(0)
    else:
        logger.error("Database fix failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()
