#!/usr/bin/env python3
"""
Simple test to verify case deletion works.
"""

import psycopg2
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
DB_PARAMS = {
    'host': 'localhost',
    'port': 5433,
    'database': 'ai_ethical_dm',
    'user': 'postgres',
    'password': 'PASS'
}

def test_deletion():
    """Test deleting a document."""
    conn = None
    cursor = None
    
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        
        # First check if document 252 exists
        cursor.execute("SELECT id, title FROM documents WHERE id = 252")
        result = cursor.fetchone()
        
        if not result:
            logger.info("Document 252 not found in database")
            
            # List some documents
            cursor.execute("SELECT id, title FROM documents ORDER BY id DESC LIMIT 5")
            docs = cursor.fetchall()
            logger.info("Recent documents:")
            for doc_id, title in docs:
                logger.info(f"  ID {doc_id}: {title}")
            return
        
        logger.info(f"Found document 252: {result[1]}")
        
        # Check for experiment_predictions referencing this document
        cursor.execute("SELECT COUNT(*) FROM experiment_predictions WHERE document_id = 252")
        pred_count = cursor.fetchone()[0]
        logger.info(f"Found {pred_count} predictions for document 252")
        
        # Try to delete predictions first if any
        if pred_count > 0:
            cursor.execute("DELETE FROM experiment_predictions WHERE document_id = 252")
            logger.info(f"Deleted {cursor.rowcount} predictions")
        
        # Now try to delete the document
        cursor.execute("DELETE FROM documents WHERE id = 252")
        
        if cursor.rowcount > 0:
            conn.commit()
            logger.info("✓ Document 252 deleted successfully!")
        else:
            logger.info("No document was deleted")
            
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"✗ Error: {str(e)}")
        
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

if __name__ == "__main__":
    test_deletion()