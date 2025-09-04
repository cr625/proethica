#!/usr/bin/env python3
"""
Direct Database Migration: Add Temporal Columns to Actions Table

Simple migration that directly connects to PostgreSQL to add the missing
temporal columns needed for enhanced scenario generation.
"""

import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    """Run the temporal columns migration directly."""
    
    # Database connection details
    conn_params = {
        'host': 'localhost',
        'port': 5432,
        'database': 'ai_ethical_dm',
        'user': 'postgres',
        'password': 'PASS'
    }
    
    try:
        # Connect to database
        conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
        
        logger.info("Connected to database, starting migration...")
        
        # Check existing columns on actions table
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'actions' 
            AND column_name IN ('temporal_boundaries', 'temporal_relations', 'process_profile');
        """)
        existing_actions_columns = [row[0] for row in cursor.fetchall()]
        logger.info(f"Existing actions temporal columns: {existing_actions_columns}")
        
        # Add missing columns to actions table
        columns_to_add = ['temporal_boundaries', 'temporal_relations', 'process_profile']
        
        for column_name in columns_to_add:
            if column_name not in existing_actions_columns:
                alter_sql = f"ALTER TABLE actions ADD COLUMN {column_name} JSON;"
                logger.info(f"Adding column to actions: {column_name}")
                cursor.execute(alter_sql)
            else:
                logger.info(f"Actions column {column_name} already exists, skipping")
        
        # Check existing columns on events table
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'events' 
            AND column_name IN ('temporal_boundaries', 'temporal_relations', 'process_profile');
        """)
        existing_events_columns = [row[0] for row in cursor.fetchall()]
        logger.info(f"Existing events temporal columns: {existing_events_columns}")
        
        # Add missing columns to events table
        for column_name in columns_to_add:
            if column_name not in existing_events_columns:
                alter_sql = f"ALTER TABLE events ADD COLUMN {column_name} JSON;"
                logger.info(f"Adding column to events: {column_name}")
                cursor.execute(alter_sql)
            else:
                logger.info(f"Events column {column_name} already exists, skipping")
        
        # Commit the changes
        conn.commit()
        logger.info("✅ Temporal columns migration completed successfully")
        
        # Verify the changes
        cursor.execute("""
            SELECT table_name, column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name IN ('actions', 'events')
            AND column_name IN ('temporal_boundaries', 'temporal_relations', 'process_profile')
            ORDER BY table_name, column_name;
        """)
        
        verification = cursor.fetchall()
        logger.info("Verification - Added columns:")
        for row in verification:
            logger.info(f"  {row[0]}.{row[1]}: {row[2]}")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        if 'conn' in locals():
            conn.rollback()
        raise
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    run_migration()
