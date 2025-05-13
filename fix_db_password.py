#!/usr/bin/env python3
"""
Fix database password in .env file and update environment variables
for use with the codespace PostgreSQL instance.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_database_url():
    """Update the database URL in the .env file"""
    # Default values for codespace
    pg_host = "localhost"
    pg_port = "5433"
    pg_user = "postgres"
    pg_password = "postgres"  # Default PostgreSQL password in codespaces
    pg_db = "ai_ethical_dm"
    
    # Load current environment variables
    if os.path.exists('.env'):
        load_dotenv()
    
    # Construct the database URL
    db_url = f"postgresql://{pg_user}:{pg_password}@{pg_host}:{pg_port}/{pg_db}"
    
    # Update environment variable
    os.environ["DATABASE_URL"] = db_url
    os.environ["SQLALCHEMY_DATABASE_URI"] = db_url
    
    # Update .env file
    if os.path.exists('.env'):
        logger.info(f"Updating DATABASE_URL in .env file to {db_url}")
        with open('.env', 'r') as f:
            lines = f.readlines()
        
        with open('.env', 'w') as f:
            db_url_found = False
            for line in lines:
                if line.strip().startswith('DATABASE_URL='):
                    f.write(f"DATABASE_URL={db_url}\n")
                    db_url_found = True
                else:
                    f.write(line)
            
            if not db_url_found:
                f.write(f"\nDATABASE_URL={db_url}\n")
    else:
        # Create new .env file
        logger.info(f"Creating new .env file with DATABASE_URL={db_url}")
        with open('.env', 'w') as f:
            f.write(f"DATABASE_URL={db_url}\n")
            f.write("ENVIRONMENT=codespace\n")
            f.write("MCP_SERVER_URL=http://localhost:5001\n")
    
    # Test connection
    try:
        import psycopg2
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        cursor.close()
        conn.close()
        logger.info(f"Successfully connected to PostgreSQL: {version}")
        return True, version
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
        return False, str(e)

if __name__ == "__main__":
    print("Fixing database connection settings for codespace...")
    success, message = fix_database_url()
    
    if success:
        print(f"Database connection fixed successfully!")
        print(f"PostgreSQL version: {message}")
        sys.exit(0)
    else:
        print(f"Failed to fix database connection: {message}")
        sys.exit(1)
