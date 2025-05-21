#!/usr/bin/env python
"""
Script to update section embeddings for existing cases.

Usage:
    python update_section_embeddings.py --case-id 123  # Process a single case
    python update_section_embeddings.py --all          # Process all cases with document structure
    python update_section_embeddings.py --limit 10     # Process up to 10 cases
"""
import os
import sys
import argparse
import logging
import time
from datetime import datetime
from flask import Flask

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"section_embeddings_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger(__name__)

def create_app():
    """Create Flask app instance for database access."""
    from app import create_app as flask_create_app
    return flask_create_app()

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Update section embeddings for cases')
    
    # Case selection options (mutually exclusive)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--case-id', type=int, help='Process a specific case by ID')
    group.add_argument('--all', action='store_true', help='Process all cases with document structure')
    
    # Additional options
    parser.add_argument('--limit', type=int, default=None, help='Limit the number of cases to process')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without making changes')
    
    return parser.parse_args()

def process_case(case_id, section_embedding_service, dry_run=False, verbose=False):
    """Process a single case to generate and store section embeddings."""
    from app.models.document import Document
    
    logger.info(f"Processing case ID: {case_id}")
    start_time = time.time()
    
    try:
        # Get the document for this case
        document = Document.query.get(case_id)
        if not document:
            logger.error(f"Document not found for case ID: {case_id}")
            return False
            
        # Check if document has structure metadata
        if not document.doc_metadata or 'document_structure' not in document.doc_metadata:
            logger.warning(f"Case {case_id} has no document structure metadata - skipping")
            return False
            
        # Log document info
        logger.info(f"Found document: {document.title} (ID: {document.id})")
        
        # Get section metadata from document_structure
        doc_structure = document.doc_metadata.get('document_structure', {})
        
        # Check if document already has section embeddings
        if 'section_embeddings' in doc_structure and not dry_run:
            existing_count = doc_structure['section_embeddings'].get('count', 0)
            logger.info(f"Document already has {existing_count} section embeddings")
            
        # Extract section metadata from document
        section_metadata = {}
        sections = doc_structure.get('sections', {})
        
        if not sections and 'section_embeddings_metadata' not in document.doc_metadata:
            logger.warning(f"Case {case_id} has no sections or section metadata - skipping")
            return False
            
        # Use existing section_embeddings_metadata if available
        if 'section_embeddings_metadata' in document.doc_metadata:
            section_metadata = document.doc_metadata['section_embeddings_metadata']
            logger.info(f"Using existing section_embeddings_metadata with {len(section_metadata)} sections")
        else:
            # Build section metadata from document structure
            for section_id, section_data in sections.items():
                if 'content' not in section_data:
                    continue
                
                section_uri = f"http://proethica.org/document/case_{case_id}/{section_id}"
                section_metadata[section_uri] = {
                    'type': section_id,
                    'content': section_data['content']
                }
            
            logger.info(f"Built section metadata for {len(section_metadata)} sections")
        
        if verbose:
            for uri, data in section_metadata.items():
                logger.info(f"Section: {uri} - Type: {data.get('type')}")
                if verbose:
                    content_excerpt = data.get('content', '')[:100].replace('\n', ' ')
                    logger.info(f"  Content (excerpt): {content_excerpt}...")
        
        if dry_run:
            logger.info(f"DRY RUN: Would process {len(section_metadata)} sections for document {case_id}")
            return True
            
        # Process document sections to generate and store embeddings
        result = section_embedding_service.process_document_sections(document.id)
        
        if result.get('success'):
            logger.info(f"Successfully processed {result.get('sections_embedded')} sections for document {case_id}")
            logger.info(f"Processing time: {time.time() - start_time:.2f} seconds")
            return True
        else:
            logger.error(f"Error processing document sections: {result.get('error')}")
            return False
            
    except Exception as e:
        logger.exception(f"Error processing case {case_id}: {str(e)}")
        return False

def find_cases_with_structure(limit=None):
    """Find all cases that have document structure metadata."""
    from app.models.document import Document
    from sqlalchemy import text
    from app import db
    
    logger.info("Finding cases with document structure metadata")
    
    try:
        # We can't directly query for JSON fields in a portable way,
        # so we'll fetch all documents and filter in Python
        query = text("SELECT id FROM documents WHERE doc_metadata IS NOT NULL")
        
        if limit:
            query = text(f"SELECT id FROM documents WHERE doc_metadata IS NOT NULL LIMIT {limit}")
            
        results = db.session.execute(query)
        
        # Filter documents with document_structure
        case_ids = []
        for row in results:
            doc = Document.query.get(row.id)
            if doc and doc.doc_metadata and 'document_structure' in doc.doc_metadata:
                case_ids.append(doc.id)
                
                # Apply limit manually if needed
                if limit and len(case_ids) >= limit:
                    break
        
        logger.info(f"Found {len(case_ids)} cases with document structure metadata")
        return case_ids
        
    except Exception as e:
        logger.exception(f"Error finding cases with structure: {str(e)}")
        return []

def main():
    """Main entry point for the script."""
    args = parse_args()
    
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Verbose logging enabled")
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        from app.services.section_embedding_service import SectionEmbeddingService
        
        # Initialize the section embedding service
        section_embedding_service = SectionEmbeddingService()
        
        # Process cases based on command-line arguments
        if args.case_id:
            # Process single case
            logger.info(f"Processing single case ID: {args.case_id}")
            success = process_case(
                args.case_id, 
                section_embedding_service, 
                dry_run=args.dry_run,
                verbose=args.verbose
            )
            if success:
                logger.info(f"Successfully processed case {args.case_id}")
            else:
                logger.error(f"Failed to process case {args.case_id}")
                
        elif args.all:
            # Process all cases with document structure
            logger.info("Processing all cases with document structure")
            case_ids = find_cases_with_structure(limit=args.limit)
            
            if not case_ids:
                logger.warning("No cases found with document structure metadata")
                return
                
            logger.info(f"Found {len(case_ids)} cases to process")
            
            # Track success/failure
            successes = 0
            failures = 0
            
            for i, case_id in enumerate(case_ids):
                logger.info(f"Processing case {i+1}/{len(case_ids)}: ID {case_id}")
                success = process_case(
                    case_id, 
                    section_embedding_service, 
                    dry_run=args.dry_run,
                    verbose=args.verbose
                )
                
                if success:
                    successes += 1
                else:
                    failures += 1
                    
                # Add a small delay between cases
                time.sleep(0.5)
            
            logger.info(f"Processing complete: {successes} successes, {failures} failures")

if __name__ == "__main__":
    start_time = time.time()
    main()
    elapsed = time.time() - start_time
    logger.info(f"Total execution time: {elapsed:.2f} seconds")
