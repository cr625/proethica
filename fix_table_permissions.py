#!/usr/bin/env python3
"""
Fix Table Permissions for ProEthica Categories

Grants proper permissions to proethica_user for the newly created
ProEthica 9-category tables.
"""

import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_permissions():
    """Fix permissions for ProEthica category tables."""
    
    # Database connection details (using postgres admin user)
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
        
        logger.info("Connected to database, fixing table permissions...")
        
        # Tables to grant permissions on
        tables = ['principles', 'obligations', 'states', 'capabilities', 'constraints']
        
        for table in tables:
            # Grant all permissions to proethica_user
            logger.info(f"Granting permissions on {table} to proethica_user...")
            cursor.execute(f"GRANT ALL PRIVILEGES ON TABLE {table} TO proethica_user;")
            
            # Also grant permissions on the sequence
            cursor.execute(f"GRANT ALL PRIVILEGES ON SEQUENCE {table}_id_seq TO proethica_user;")
        
        # Commit the changes
        conn.commit()
        logger.info("✅ Table permissions fixed successfully")
        
        # Verify the permissions
        cursor.execute("""
            SELECT table_name, privilege_type 
            FROM information_schema.role_table_grants 
            WHERE grantee = 'proethica_user'
            AND table_name IN ('principles', 'obligations', 'states', 'capabilities', 'constraints')
            ORDER BY table_name, privilege_type;
        """)
        
        verification = cursor.fetchall()
        logger.info("Verification - Granted permissions:")
        for row in verification:
            logger.info(f"  {row[0]}: {row[1]}")
        
    except Exception as e:
        logger.error(f"Permission fix failed: {e}")
        if 'conn' in locals():
            conn.rollback()
        raise
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    fix_permissions()
