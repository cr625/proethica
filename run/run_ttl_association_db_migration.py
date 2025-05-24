#!/usr/bin/env python3
"""
Database migration script for the TTL-based section-triple association system.

This script applies the SQL migration to create the necessary tables
for the section-triple association system.
"""

import os
import sys
import logging
import argparse
from sqlalchemy import create_engine, text

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Apply database migrations for the TTL-based section-triple association system",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument('--db-url', type=str, default=None,
                      help='Database connection URL (defaults to environment variable)')
    parser.add_argument('--migration-file', type=str, 
                      default='ttl_triple_association/create_section_associations_table.sql',
                      help='Path to SQL migration file')
    
    return parser.parse_args()

def apply_migration(db_url, migration_file):
    """
    Apply the SQL migration to the database.
    
    Args:
        db_url: Database URL
        migration_file: Path to SQL migration file
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # Verify file exists
        if not os.path.isfile(migration_file):
            logger.error(f"Migration file not found: {migration_file}")
            return False
        
        # Read migration SQL
        with open(migration_file, 'r') as f:
            migration_sql = f.read()
        
        # Connect to database
        logger.info(f"Connecting to database...")
        engine = create_engine(db_url)
        
        # Execute migration
        logger.info(f"Applying migration from {migration_file}...")
        with engine.connect() as connection:
            connection.execute(text(migration_sql))
            connection.commit()
        
        logger.info("Migration applied successfully")
        return True
        
    except Exception as e:
        logger.error(f"Error applying migration: {e}")
        return False

def main():
    """Main entry point."""
    args = parse_args()
    
    # Get database URL
    db_url = args.db_url or os.environ.get(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5433/ai_ethical_dm"
    )
    
    # Apply migration
    success = apply_migration(db_url, args.migration_file)
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
