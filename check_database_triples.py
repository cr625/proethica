#!/usr/bin/env python3
"""
Database Triple Inspection Tool
-----------------------------
This script directly queries the database to examine how triples
are stored for a specific case. It uses raw SQL queries to
examine table structure and triple storage patterns.

This is helpful for debugging when higher-level API functions
are not finding expected triples.
"""

import os
import sys
import json
import psycopg2
from datetime import datetime

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

def inspect_entity_triples_table():
    """Print the structure of the entity_triples table."""
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    try:
        # Get column information
        cursor.execute("""
            SELECT column_name, data_type, character_maximum_length
            FROM information_schema.columns
            WHERE table_name = 'entity_triples'
            ORDER BY ordinal_position;
        """)
        
        print("\n=== ENTITY_TRIPLES TABLE STRUCTURE ===")
        columns = cursor.fetchall()
        for col in columns:
            print(f"{col[0]} ({col[1]}" + (f"({col[2]})" if col[2] else "") + ")")
        
        # Get count of triples
        cursor.execute("SELECT COUNT(*) FROM entity_triples")
        count = cursor.fetchone()
        print(f"\nTotal triples in database: {count[0]}")
        
        # Get distinct entity_types and temporal_region_types
        cursor.execute("SELECT DISTINCT entity_type FROM entity_triples")
        entity_types = cursor.fetchall()
        print("\nDistinct entity_types:")
        for etype in entity_types:
            cursor.execute("SELECT COUNT(*) FROM entity_triples WHERE entity_type = %s", (etype[0],))
            type_count = cursor.fetchone()
            print(f"  {etype[0]}: {type_count[0]} triples")
        
        cursor.execute("SELECT DISTINCT temporal_region_type FROM entity_triples")
        region_types = cursor.fetchall()
        print("\nDistinct temporal_region_types:")
        for rtype in region_types:
            cursor.execute("SELECT COUNT(*) FROM entity_triples WHERE temporal_region_type = %s", (rtype[0],))
            type_count = cursor.fetchone()
            print(f"  {rtype[0]}: {type_count[0]} triples")
            
    except Exception as e:
        print(f"Error inspecting table: {str(e)}")
    finally:
        cursor.close()
        conn.close()

def find_triples_for_case(case_id):
    """
    Find all triples that might be related to the specified case ID,
    using multiple search strategies.
    """
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    try:
        print(f"\n=== SEARCHING FOR TRIPLES RELATED TO CASE {case_id} ===")
        
        # Strategy 1: By temporal_region_type
        cursor.execute("""
            SELECT COUNT(*), entity_type 
            FROM entity_triples 
            WHERE temporal_region_type = %s
            GROUP BY entity_type
        """, (str(case_id),))
        
        results = cursor.fetchall()
        if results:
            print("\nTriples found by temporal_region_type:")
            for count, entity_type in results:
                print(f"  {count} triples with entity_type='{entity_type}'")
        else:
            print("\nNo triples found by temporal_region_type")
        
        # Strategy 2: By subject containing case ID
        case_uri = f"http://proethica.org/cases/{case_id}"
        cursor.execute("""
            SELECT COUNT(*), entity_type 
            FROM entity_triples 
            WHERE subject = %s
            GROUP BY entity_type
        """, (case_uri,))
        
        results = cursor.fetchall()
        if results:
            print("\nTriples found by subject URI:")
            for count, entity_type in results:
                print(f"  {count} triples with entity_type='{entity_type}'")
        else:
            print("\nNo triples found by subject URI")
        
        # Strategy 3: By metadata containing case ID
        cursor.execute("""
            SELECT COUNT(*) 
            FROM entity_triples 
            WHERE triple_metadata::text LIKE %s
        """, (f"%{case_id}%",))
        
        count = cursor.fetchone()
        if count and count[0] > 0:
            print(f"\n{count[0]} triples found by metadata containing case ID")
        else:
            print("\nNo triples found by metadata containing case ID")
        
        # Strategy 4: Get some sample triples for manual inspection
        cursor.execute("""
            SELECT id, subject, predicate, object_uri, object_literal, is_literal, 
                entity_type, temporal_region_type, graph, triple_metadata
            FROM entity_triples 
            WHERE subject = %s
            LIMIT 5
        """, (case_uri,))
        
        triples = cursor.fetchall()
        if triples:
            print("\nSample triples for manual inspection:")
            for t in triples:
                print(f"\nID: {t[0]}")
                print(f"  Subject: {t[1]}")
                print(f"  Predicate: {t[2]}")
                print(f"  Object: {t[3] if not t[5] else t[4]}")
                print(f"  entity_type: {t[6]}")
                print(f"  temporal_region_type: {t[7]}")
                print(f"  graph: {t[8]}")
                print(f"  metadata: {t[9]}")
        
    except Exception as e:
        print(f"Error searching for triples: {str(e)}")
    finally:
        cursor.close()
        conn.close()

def check_document_exists(case_id):
    """Check if a document with the given ID exists."""
    conn = get_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, title, doc_type, doc_metadata
            FROM documents
            WHERE id = %s
        """, (case_id,))
        
        doc = cursor.fetchone()
        if doc:
            print(f"\n=== DOCUMENT {case_id} DETAILS ===")
            print(f"ID: {doc[0]}")
            print(f"Title: {doc[1]}")
            print(f"Type: {doc[2]}")
            print(f"Metadata: {doc[3]}")
            return True
        else:
            print(f"\nNo document found with ID {case_id}")
            return False
            
    except Exception as e:
        print(f"Error checking document: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def check_correct_triple_type(case_id, expected_entity_type='document'):
    """
    Check if the ontology_integration.py is using the correct entity_type
    and temporal_region_type when storing triples.
    """
    conn = get_connection()
    if not conn:
        return
    
    cursor = conn.cursor()
    try:
        # First, check what temporal_region_type is being used
        cursor.execute("""
            SELECT entity_type, temporal_region_type
            FROM entity_triples
            WHERE subject LIKE %s
            LIMIT 1
        """, (f"%cases/{case_id}%",))
        
        result = cursor.fetchone()
        
        if result:
            actual_entity_type, temp_region_type = result
            print(f"\n=== TRIPLE STORAGE PATTERN CHECK ===")
            print(f"Expected entity_type: '{expected_entity_type}'")
            print(f"Actual entity_type: '{actual_entity_type}'")
            print(f"Temporal region type: '{temp_region_type}'")
            
            if actual_entity_type != expected_entity_type:
                print("\nWARNING: Triples are not being stored with the expected entity_type!")
                print(f"The correct_query_triples.py script is looking for entity_type='{expected_entity_type}'")
                print(f"But triples are being stored with entity_type='{actual_entity_type}'")
        else:
            print(f"\nNo triples found with subject containing 'cases/{case_id}'")
            
    except Exception as e:
        print(f"Error checking triple type: {str(e)}")
    finally:
        cursor.close()
        conn.close()

def main():
    """Main function to run the checks."""
    if len(sys.argv) < 2:
        print("Usage: python check_database_triples.py <case_id>")
        return 1
    
    try:
        case_id = int(sys.argv[1])
    except ValueError:
        print("Error: Case ID must be an integer")
        return 1
    
    # Check if the document exists
    doc_exists = check_document_exists(case_id)
    
    # Check table structure
    inspect_entity_triples_table()
    
    # Search for triples related to the case
    find_triples_for_case(case_id)
    
    # Check if triples are being stored with the correct type
    check_correct_triple_type(case_id)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
