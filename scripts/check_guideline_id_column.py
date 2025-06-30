#!/usr/bin/env python3
"""
Check if guideline_id column exists in entity_triples table
"""

import os
import sys
import psycopg2

# Database connection parameters
DB_NAME = "ai_ethical_dm"
DB_USER = "postgres"
DB_PASSWORD = "PASS"
DB_HOST = "localhost"
DB_PORT = "5433"

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

def check_guideline_id_column():
    """Check if guideline_id column exists in entity_triples table."""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    
    # Check if guideline_id column exists
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.columns 
            WHERE table_name = 'entity_triples' 
            AND column_name = 'guideline_id'
        );
    """)
    
    exists = cursor.fetchone()[0]
    
    print(f"guideline_id column exists in entity_triples table: {exists}")
    
    if exists:
        # Check column details
        cursor.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = 'entity_triples' 
            AND column_name = 'guideline_id';
        """)
        
        column_info = cursor.fetchone()
        print(f"\nColumn details:")
        print(f"  Name: {column_info[0]}")
        print(f"  Type: {column_info[1]}")
        print(f"  Nullable: {column_info[2]}")
        print(f"  Default: {column_info[3]}")
        
        # Check foreign key constraint
        cursor.execute("""
            SELECT 
                tc.constraint_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
                AND tc.table_name = 'entity_triples'
                AND kcu.column_name = 'guideline_id';
        """)
        
        fk_info = cursor.fetchone()
        if fk_info:
            print(f"\nForeign key constraint:")
            print(f"  Constraint name: {fk_info[0]}")
            print(f"  References: {fk_info[2]}.{fk_info[3]}")
        
        # Check if there are any values
        cursor.execute("""
            SELECT COUNT(*) FROM entity_triples WHERE guideline_id IS NOT NULL;
        """)
        count = cursor.fetchone()[0]
        print(f"\nRows with guideline_id values: {count}")
        
    else:
        print("\nThe guideline_id column does NOT exist in entity_triples table!")
        print("This explains the 'column does not exist' error.")
        print("\nTo fix this, you need to run the migration script:")
        print("  python scripts/database_migrations/create_guidelines_tables.py")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    check_guideline_id_column()