#!/usr/bin/env python3
"""
Script to debug document table issues
"""

import sys
import os
import logging
from sqlalchemy import create_engine, text
import json

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("debug_documents")

def debug_documents():
    """
    Check document tables and their contents to debug display issues
    """
    try:
        # Connect with properly formatted URL
        engine = create_engine(
            "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
        )
        logger.info("Connected to database")

        with engine.connect() as conn:
            # Check tables
            tables = conn.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            )).fetchall()
            logger.info(f"Tables in database: {[t[0] for t in tables]}")
            
            # Check document table structure
            document_cols = conn.execute(text(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'document'"
            )).fetchall()
            logger.info(f"'document' table columns: {document_cols}")
            
            # Check documents table structure
            documents_cols = conn.execute(text(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'documents'"
            )).fetchall()
            logger.info(f"'documents' table columns: {documents_cols}")
            
            # Check contents of document table with the correct columns
            document_rows = conn.execute(text(
                "SELECT id, title, content_type FROM document"
            )).fetchall()
            logger.info(f"'document' table records: {document_rows}")
            
            # Check content in document table
            for row in document_rows:
                content_check = conn.execute(text(
                    "SELECT LENGTH(content) FROM document WHERE id = :id"
                ), {"id": row[0]}).fetchone()
                logger.info(f"'document' table content length for ID {row[0]}: {content_check[0] if content_check else 'NULL'}")
            
            # Check contents of documents table
            documents_rows = conn.execute(text(
                "SELECT id, title, document_type, world_id FROM documents"
            )).fetchall()
            logger.info(f"'documents' table records: {documents_rows}")
            
            # Check content in documents table
            for row in documents_rows:
                content_check = conn.execute(text(
                    "SELECT LENGTH(content) FROM documents WHERE id = :id"
                ), {"id": row[0]}).fetchone()
                logger.info(f"'documents' table content length for ID {row[0]}: {content_check[0] if content_check else 'NULL'}")
            
            # Check case studies with world_id=1
            case_studies = conn.execute(text(
                "SELECT id, title, document_type, world_id FROM documents WHERE document_type = 'case_study' AND world_id = 1"
            )).fetchall()
            logger.info(f"Case studies in world 1: {case_studies}")
            
            # Check if any documents have world_id as NULL
            null_world_docs = conn.execute(text(
                "SELECT id, title, document_type FROM documents WHERE world_id IS NULL"
            )).fetchall()
            logger.info(f"Documents with null world_id: {null_world_docs}")
            
            # Check if there are any documents with mistyped document_type
            doc_types = conn.execute(text(
                "SELECT DISTINCT document_type FROM documents"
            )).fetchall()
            logger.info(f"Distinct document_types: {doc_types}")
            
            return True
    except Exception as e:
        logger.error(f"Error debugging documents: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if debug_documents():
        logger.info("Document debugging completed successfully")
        sys.exit(0)
    else:
        logger.error("Document debugging failed")
        sys.exit(1)
