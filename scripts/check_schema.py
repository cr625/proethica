#!/usr/bin/env python3
"""
Check database schema
"""

import os
import sys
import psycopg2

# Database connection parameters
DB_NAME = "ai_ethical_dm"
DB_USER = "postgres"
DB_PASSWORD = "PASS"  # Replace with actual password if needed
DB_HOST = "localhost"
DB_PORT = "5433"      # PostgreSQL port used in Docker

def get_connection():
    """Get a PostgreSQL database connection."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {str(e)}")
        return None

def check_entity_triples_schema():
    """Check the schema of the entity_triples table."""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    # Query the table schema
    cursor.execute("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'entity_triples'
    """)
    
    columns = cursor.fetchall()
    
    print("ENTITY_TRIPLES TABLE SCHEMA:")
    print("="*40)
    for column in columns:
        print(f"{column[0]}: {column[1]}")
    
    # Check sample triples
    cursor.execute("""
        SELECT *
        FROM entity_triples
        LIMIT 1
    """)
    
    sample = cursor.fetchone()
    if sample:
        print("\nSAMPLE TRIPLE:")
        print("="*40)
        for i, column in enumerate(columns):
            print(f"{column[0]}: {sample[i]}")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    check_entity_triples_schema()
