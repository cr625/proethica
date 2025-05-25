#!/usr/bin/env python3
"""
Script to delete Case 187 from the database before reimporting it with improved triples
"""

import sys
import os
import logging
import psycopg2

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("delete_case_187")

def get_db_connection():
    """Get a connection to the database"""
    try:
        conn = psycopg2.connect(
            host="localhost",
            database="ai_ethical_dm",
            user="postgres",
            password="PASS",
            port=5433
        )
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        sys.exit(1)

def delete_case_187():
    """Delete Case 187 from the database"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if case exists
        cursor.execute("SELECT id, title FROM documents WHERE id = 187")
        case = cursor.fetchone()
        
        if not case:
            logger.info("Case 187 not found in database, nothing to delete")
            conn.close()
            return
        
        case_id, case_title = case
        logger.info(f"Found case to delete: ID {case_id} - '{case_title}'")
        
        # Delete entity triples first (foreign key constraint)
        logger.info("Deleting entity triples for Case 187...")
        cursor.execute("DELETE FROM entity_triples WHERE entity_id = 187 AND entity_type = 'document'")
        triple_count = cursor.rowcount
        logger.info(f"Deleted {triple_count} entity triples")
        
        # Delete document chunks (foreign key constraint)
        logger.info("Deleting document chunks for Case 187...")
        cursor.execute("DELETE FROM document_chunks WHERE document_id = 187")
        chunk_count = cursor.rowcount
        logger.info(f"Deleted {chunk_count} document chunks")
        
        # Delete the document
        logger.info("Deleting document for Case 187...")
        cursor.execute("DELETE FROM documents WHERE id = 187")
        doc_count = cursor.rowcount
        logger.info(f"Deleted {doc_count} document record")
        
        # Commit the changes
        conn.commit()
        logger.info("Successfully deleted Case 187 and all related data")
        
        conn.close()
    except Exception as e:
        logger.error(f"Error deleting Case 187: {e}")
        if conn:
            conn.close()
        sys.exit(1)

if __name__ == "__main__":
    delete_case_187()
