#!/usr/bin/env python
"""
Migration script to update document metadata for cases with section embeddings.

This script:
1. Finds all cases that have entries in the DocumentSection table
2. Updates their document_structure metadata to include section_embeddings information
3. Shows the count of documents updated

Usage:
    python migrate_section_embeddings_metadata.py [--dry-run]
"""

import sys
import json
import time
import logging
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Determine if we're in dry run mode
dry_run = '--dry-run' in sys.argv

# Database configuration - adjust as needed
db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5433/ai_ethical_dm')

def main():
    """Main migration function."""
    logger.info(f"Starting section embeddings metadata migration (dry run: {dry_run})")
    
    # Create database engine and session
    engine = create_engine(db_url)
    session_factory = sessionmaker(bind=engine)
    Session = scoped_session(session_factory)
    session = Session()
    
    try:
        # Find all documents that have section embeddings but might be missing metadata
        query = """
        SELECT 
            ds.document_id,
            COUNT(ds.id) as section_count,
            d.doc_metadata
        FROM 
            document_sections ds
        JOIN 
            documents d ON ds.document_id = d.id
        GROUP BY 
            ds.document_id, d.doc_metadata, d.id
        ORDER BY 
            ds.document_id
        """
        
        results = session.execute(text(query))
        
        # Process each document
        documents_processed = 0
        documents_updated = 0
        documents_already_ok = 0
        
        for row in results:
            document_id = row.document_id
            section_count = row.section_count
            doc_metadata = row.doc_metadata
            
            documents_processed += 1
            
            # Skip documents with no metadata
            if not doc_metadata:
                logger.warning(f"Document {document_id} has no metadata, skipping")
                continue
            
            # Check if the document already has correct section_embeddings metadata
            if ('document_structure' in doc_metadata and 
                'section_embeddings' in doc_metadata['document_structure'] and
                doc_metadata['document_structure']['section_embeddings'].get('count') == section_count):
                logger.info(f"Document {document_id} already has correct section_embeddings metadata ({section_count} sections)")
                documents_already_ok += 1
                continue
                
            # Document needs update
            logger.info(f"Updating document {document_id} with {section_count} sections")
            
            # Make sure document_structure exists
            if 'document_structure' not in doc_metadata:
                doc_metadata['document_structure'] = {}
            
            # Update section_embeddings metadata
            doc_metadata['document_structure']['section_embeddings'] = {
                'count': section_count,
                'updated_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'),
                'storage_type': 'pgvector',
                'embedding_dimension': 384
            }
            
            if not dry_run:
                # Update the document
                update_query = """
                UPDATE documents
                SET doc_metadata = :metadata
                WHERE id = :document_id
                """
                
                # Convert metadata to JSON string
                metadata_json = json.dumps(doc_metadata)
                
                # Execute update
                session.execute(
                    text(update_query),
                    {'metadata': metadata_json, 'document_id': document_id}
                )
                
                documents_updated += 1
            else:
                # In dry run mode, just count what would be updated
                documents_updated += 1
        
        # Commit changes if not in dry run mode
        if not dry_run:
            session.commit()
            logger.info(f"Successfully committed changes to the database")
        
        # Log summary
        logger.info(f"Migration completed: {documents_processed} documents processed")
        logger.info(f"  - {documents_updated} documents updated with section_embeddings metadata")
        logger.info(f"  - {documents_already_ok} documents already had correct metadata")
        logger.info(f"  - {documents_processed - documents_updated - documents_already_ok} documents skipped")
        
    except Exception as e:
        logger.exception(f"Error during migration: {str(e)}")
        if not dry_run:
            session.rollback()
        return 1
    finally:
        session.close()
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
