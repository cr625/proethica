#!/usr/bin/env python
"""
Restore Guideline Entry for Document 190

This script creates a guideline record in the guidelines table for document ID 190,
which is the 'Engineering Ethics' document. This ensures that the UI can properly
recognize document 190 as a guideline document when the server is restarted.
"""

import os
import sys
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

def check_document_exists():
    """Check if document 190 exists and get its details."""
    conn = get_connection()
    if not conn:
        return False, {}
    
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, title, document_type, doc_metadata
            FROM documents
            WHERE id = 190
        """)
        
        doc = cursor.fetchone()
        if doc:
            doc_info = {
                'id': doc[0],
                'title': doc[1],
                'document_type': doc[2],
                'doc_metadata': doc[3]
            }
            return True, doc_info
        else:
            print("No document found with ID 190")
            return False, {}
            
    except Exception as e:
        print(f"Error checking document: {str(e)}")
        return False, {}
    finally:
        cursor.close()
        conn.close()

def restore_guideline_entry(doc_info):
    """Restore the guideline entry for document 190."""
    conn = get_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    try:
        # Check if guideline already exists
        cursor.execute("SELECT COUNT(*) FROM guidelines WHERE id = 190")
        guideline_exists = cursor.fetchone()[0] > 0
        
        if guideline_exists:
            print("Guideline 190 already exists in the database")
            return True
        
        # Create the guideline entry
        cursor.execute("""
            INSERT INTO guidelines (id, title, description, world_id, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            190,
            doc_info['title'],
            "Engineering Ethics Guidelines",
            1,  # world_id from the URL the user mentioned
            datetime.now(),
            datetime.now()
        ))
        
        # Update the document to reference this guideline
        cursor.execute("""
            UPDATE documents 
            SET doc_metadata = jsonb_set(doc_metadata, '{guideline_id}', %s)
            WHERE id = 190
        """, ('190',))
        
        conn.commit()
        print("Successfully created guideline entry for document 190")
        return True
    
    except Exception as e:
        conn.rollback()
        print(f"Error restoring guideline entry: {str(e)}")
        return False
    finally:
        cursor.close()
        conn.close()

def main():
    """Main function to restore the guideline entry."""
    print("=" * 70)
    print("Restoring Guideline Entry for Document 190")
    print("=" * 70)
    
    # Check if document 190 exists
    doc_exists, doc_info = check_document_exists()
    if not doc_exists:
        print("Document 190 does not exist. Cannot restore guideline entry.")
        return 1
    
    # Show document information
    print(f"Document ID: {doc_info['id']}")
    print(f"Title: {doc_info['title']}")
    print(f"Type: {doc_info['document_type']}")
    print(f"Metadata: {doc_info['doc_metadata']}")
    
    # Restore the guideline entry
    if restore_guideline_entry(doc_info):
        print("\nSuccess! Guideline entry for document 190 has been restored.")
        print("\nNote: You'll need to restart the server for this change to take effect.")
        print("After restarting, the UI should display the Engineering Ethics document properly.")
        
        print("\nTo regenerate the guideline triples, you may need to:")
        print("1. Start the server")
        print("2. Open document 190 in the UI")
        print("3. Use the 'Extract Guideline Concepts' feature in the UI")
        
        return 0
    else:
        print("\nFailed to restore guideline entry.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
