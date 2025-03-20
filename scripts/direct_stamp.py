#!/usr/bin/env python3
"""
Script to directly stamp the database with a specific revision.
"""
import os
import sys
import psycopg2

def stamp_database():
    """Directly stamp the database with the specific revision."""
    # The specific revision ID your app is looking for
    REVISION_ID = 'd9c222ce7986'
    
    # Database connection parameters
    db_params = {
        'dbname': 'ai_ethical_dm',
        'user': 'postgres',
        'password': 'PASS',
        'host': 'localhost'
    }
    
    try:
        # Connect to the database
        conn = psycopg2.connect(**db_params)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Create the alembic_version table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS alembic_version (
            version_num VARCHAR(32) NOT NULL,
            CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
        )
        """)
        
        # Clear any existing entries
        cursor.execute("DELETE FROM alembic_version")
        
        # Insert the specific revision
        cursor.execute("INSERT INTO alembic_version (version_num) VALUES (%s)", (REVISION_ID,))
        
        print(f"Successfully stamped database with revision {REVISION_ID}")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    stamp_database()