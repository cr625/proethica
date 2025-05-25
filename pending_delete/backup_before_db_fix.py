#!/usr/bin/env python3
"""
Create a database backup before applying database schema fixes.
This helps protect against data loss during schema modifications.
"""

import os
import sys
import logging
import subprocess
import datetime
import argparse

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

def create_backup(db_params, backup_file=None, note=None):
    """Create a database backup using pg_dump."""
    
    # Generate a default backup filename with timestamp if none provided
    if not backup_file:
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        if note:
            safe_note = ''.join(c if c.isalnum() else '_' for c in note).lower()
            backup_file = f"backup_{safe_note}_{timestamp}.dump"
        else:
            backup_file = f"ai_ethical_dm_backup_{timestamp}.dump"
    
    # Ensure backups directory exists
    os.makedirs('backups', exist_ok=True)
    backup_path = os.path.join('backups', backup_file)
    
    # Set environment variables for pg_dump
    env = os.environ.copy()
    if db_params['password']:
        env['PGPASSWORD'] = db_params['password']
    
    # Build pg_dump command
    cmd = [
        'pg_dump',
        '-h', db_params['host'],
        '-p', str(db_params['port']),
        '-U', db_params['user'],
        '-F', 'c',  # Custom format for pg_restore
        '-b',       # Include large objects
        '-v',       # Verbose
        '-f', backup_path,
        db_params['dbname']
    ]
    
    logger.info(f"Creating database backup: {backup_path}")
    
    try:
        # Execute pg_dump
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        
        if result.returncode == 0:
            logger.info(f"Backup created successfully: {backup_path}")
            logger.info(f"Output: {result.stdout}")
            return backup_path
        else:
            logger.error(f"Error creating backup: {result.stderr}")
            return None
    
    except Exception as e:
        logger.error(f"Exception while creating backup: {str(e)}")
        return None

def main():
    """Main function to create database backup."""
    
    parser = argparse.ArgumentParser(description='Create a database backup before applying schema fixes.')
    parser.add_argument('--note', help='A note to include in the backup filename', default="before_db_fix")
    parser.add_argument('--output', help='Output filename for the backup', default=None)
    args = parser.parse_args()
    
    # Get the database URL and parse it
    db_url = get_db_url()
    db_params = parse_db_url(db_url)
    
    # Create the database backup
    backup_path = create_backup(db_params, args.output, args.note)
    
    if backup_path:
        logger.info(f"Database backup created at: {backup_path}")
        logger.info("You can now safely apply database schema fixes.")
        sys.exit(0)
    else:
        logger.error("Failed to create database backup!")
        logger.error("It's recommended NOT to proceed with database schema modifications.")
        sys.exit(1)

if __name__ == "__main__":
    main()
