#!/usr/bin/env python3
"""
Update Document Structure Storage
--------------------------------
Implements Phase 2.4 of the document structure enhancement plan:
- Updates existing documents to include document structure triples
- Formalizes the doc_metadata schema for structure information
- Ensures backward compatibility with existing documents
"""

import os
import sys
import logging
import argparse
import json
from datetime import datetime
import uuid

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

# Import the database module directly from nspe-pipeline
sys.path.insert(0, os.path.join(os.path.abspath(os.path.dirname(__file__)), 'nspe-pipeline'))
from utils.database import get_db_connection
from app.services.case_processing.pipeline_steps.document_structure_annotation_step import DocumentStructureAnnotationStep

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_document(conn, document_id):
    """Get document by ID"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, document_type, doc_metadata
        FROM documents
        WHERE id = %s
    """, (document_id,))
    
    doc = cursor.fetchone()
    if not doc:
        return None
    
    cursor.close()
    
    # Convert to dict and handle doc_metadata correctly
    document = {
        'id': doc[0],
        'title': doc[1],
        'document_type': doc[2],
        'doc_metadata': {}
    }
    
    # Handle doc_metadata which could be a string or already a dict
    if doc[3]:
        if isinstance(doc[3], str):
            document['doc_metadata'] = json.loads(doc[3])
        else:
            document['doc_metadata'] = doc[3]
    
    return document

def update_document(conn, document, dry_run=False):
    """
    Update a single document with document structure annotations.
    
    Args:
        conn: Database connection
        document: Document dict with id, title, and doc_metadata
        dry_run: If True, don't save changes to database
    
    Returns:
        dict: Result of the update operation
    """
    logger.info(f"Processing document ID: {document['id']} - '{document['title']}'")
    
    # Skip if document already has structure information
    if 'document_structure' in document['doc_metadata']:
        logger.info(f"Document {document['id']} already has structure information, skipping.")
        return {
            'status': 'skipped',
            'reason': 'already_has_structure',
            'document_id': document['id']
        }
    
    # Check if document has the necessary sections
    metadata = document['doc_metadata']
    sections = metadata.get('sections', {})
    
    if not sections:
        logger.warning(f"Document {document['id']} has no sections data, skipping.")
        return {
            'status': 'skipped',
            'reason': 'no_sections',
            'document_id': document['id']
        }
    
    # Prepare input data for document structure annotation step
    input_data = {
        'status': 'success',
        'case_number': metadata.get('case_number', ''),
        'year': metadata.get('year', ''),
        'title': document['title'],
        'sections': sections,
        'questions_list': metadata.get('questions_list', []),
        'conclusion_items': metadata.get('conclusion_items', [])
    }
    
    # Create and run document structure annotation step
    structure_step = DocumentStructureAnnotationStep()
    result = structure_step.process(input_data)
    
    if result.get('status') != 'success':
        logger.error(f"Failed to generate document structure for {document['id']}: {result.get('message')}")
        return {
            'status': 'error',
            'reason': result.get('message'),
            'document_id': document['id']
        }
    
    # Update document metadata with structure information
    if not dry_run:
        # Get current document metadata and update it
        doc_metadata = document['doc_metadata']
        
        # Add document structure data
        doc_metadata['document_structure'] = {
            'document_uri': result['document_structure']['document_uri'],
            'structure_triples': result['document_structure']['structure_triples'],
            'annotation_timestamp': datetime.utcnow().isoformat()
        }
        
        # Add section embeddings metadata
        doc_metadata['section_embeddings_metadata'] = result['section_embeddings_metadata']
        
        # Update document record in database
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE documents
            SET doc_metadata = %s
            WHERE id = %s
        """, (json.dumps(doc_metadata), document['id']))
        
        conn.commit()
        cursor.close()
        
        logger.info(f"Document {document['id']} updated with structure information.")
        return {
            'status': 'updated',
            'document_id': document['id'],
            'triples_count': len(result['document_structure']['graph'])
        }
    else:
        logger.info(f"Dry run: Would update document {document['id']} with structure information.")
        return {
            'status': 'dry_run',
            'document_id': document['id'],
            'triples_count': len(result['document_structure']['graph'])
        }

def get_case_studies(conn, case_id=None):
    """Get all case study documents or a specific one if case_id is provided"""
    cursor = conn.cursor()
    
    if case_id:
        cursor.execute("""
            SELECT id, title, document_type, doc_metadata
            FROM documents
            WHERE document_type = 'case_study' AND id = %s
        """, (case_id,))
    else:
        cursor.execute("""
            SELECT id, title, document_type, doc_metadata
            FROM documents
            WHERE document_type = 'case_study'
        """)
    
    documents = []
    for doc in cursor.fetchall():
        document = {
            'id': doc[0],
            'title': doc[1],
            'document_type': doc[2],
            'doc_metadata': {}
        }
        
        # Handle doc_metadata which could be a string or already a dict
        if doc[3]:
            if isinstance(doc[3], str):
                document['doc_metadata'] = json.loads(doc[3])
            else:
                document['doc_metadata'] = doc[3]
                
        documents.append(document)
    
    cursor.close()
    return documents

def update_all_documents(conn, case_id=None, dry_run=False):
    """
    Update all case study documents with document structure annotations.
    
    Args:
        conn: Database connection
        case_id: Optional specific case ID to update
        dry_run: If True, don't save changes to database
    
    Returns:
        dict: Summary of update operations
    """
    # Initialize counters
    stats = {
        'total': 0,
        'updated': 0,
        'skipped': 0,
        'error': 0,
        'skipped_reasons': {},
        'errors': []
    }
    
    # Get case study documents
    documents = get_case_studies(conn, case_id)
    stats['total'] = len(documents)
    
    logger.info(f"Found {len(documents)} case study documents to process.")
    
    # Process each document
    for document in documents:
        result = update_document(conn, document, dry_run)
        
        # Update statistics
        stats[result['status']] = stats.get(result['status'], 0) + 1
        
        if result['status'] == 'skipped':
            reason = result['reason']
            stats['skipped_reasons'][reason] = stats['skipped_reasons'].get(reason, 0) + 1
        
        if result['status'] == 'error':
            stats['errors'].append({
                'document_id': result['document_id'],
                'reason': result['reason']
            })
    
    return stats

def main():
    """Main entry point for script."""
    parser = argparse.ArgumentParser(description='Update document storage with structure triples')
    parser.add_argument('--case-id', type=int, help='Specific case ID to update')
    parser.add_argument('--dry-run', action='store_true', help="Don't save changes to database")
    args = parser.parse_args()
    
    # Get database connection
    conn = get_db_connection()
    
    try:
        logger.info("Starting document structure storage update...")
        
        if args.case_id:
            logger.info(f"Processing specific case ID: {args.case_id}")
        
        if args.dry_run:
            logger.info("DRY RUN MODE: No changes will be saved to the database")
        
        # Run update operation
        stats = update_all_documents(conn, case_id=args.case_id, dry_run=args.dry_run)
        
        # Print summary
        logger.info("="*50)
        logger.info("Document Structure Update Summary")
        logger.info("="*50)
        logger.info(f"Total documents processed: {stats['total']}")
        logger.info(f"Documents updated: {stats['updated']}")
        logger.info(f"Documents skipped: {stats['skipped']}")
        logger.info(f"Documents with errors: {stats.get('error', 0)}")
        
        if stats.get('skipped', 0) > 0:
            logger.info("\nSkipped reasons:")
            for reason, count in stats['skipped_reasons'].items():
                logger.info(f"  {reason}: {count}")
        
        if stats.get('error', 0) > 0:
            logger.info("\nErrors:")
            for error in stats['errors']:
                logger.info(f"  Document {error['document_id']}: {error['reason']}")
        
        logger.info("="*50)
        
        if args.dry_run:
            logger.info("DRY RUN COMPLETE: Run without --dry-run to apply changes")
        else:
            logger.info("UPDATE COMPLETE")
    
    finally:
        conn.close()

if __name__ == "__main__":
    main()
