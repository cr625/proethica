#!/usr/bin/env python3
"""
Process a document and associate RDF triples with its sections based on semantic similarity.
"""
import os
import sys
import argparse
import json
import logging
from dotenv import load_dotenv
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def create_app_context():
    """Create a Flask app context for database operations."""
    try:
        from app import create_app
        app = create_app()
        return app.app_context()
    except Exception as e:
        logger.exception(f"Error creating app context: {str(e)}")
        sys.exit(1)

def get_document_info(document_id):
    """Get basic information about a document."""
    from app.models.document import Document
    
    try:
        document = Document.query.get(document_id)
        if not document:
            logger.error(f"Document not found: {document_id}")
            return None
            
        return {
            'id': document.id,
            'title': document.title,
            'type': document.document_type,
            'has_sections': bool(Document.query.join(Document.document_sections).filter(Document.id == document_id).count())
        }
    except Exception as e:
        logger.exception(f"Error getting document info: {str(e)}")
        return None

def associate_triples_with_document(document_id, triple_types=None, threshold=0.6, force=False):
    """Associate RDF triples with document sections."""
    from app.models.document import Document
    from app.models.document_section import DocumentSection
    
    try:
        # Check if document exists
        document = Document.query.get(document_id)
        if not document:
            logger.error(f"Document not found: {document_id}")
            return False
        
        # Check if document has sections
        sections_count = DocumentSection.query.filter_by(document_id=document_id).count()
        if sections_count == 0:
            logger.error(f"Document {document_id} has no sections. Please generate embeddings first.")
            return False
        
        # Check if document already has triple associations
        if not force and document.doc_metadata and isinstance(document.doc_metadata, dict):
            if ('document_structure' in document.doc_metadata and 
                'triple_associations' in document.doc_metadata['document_structure']):
                logger.warning(f"Document {document_id} already has triple associations.")
                logger.warning("Use --force to regenerate. Skipping...")
                return False
        
        # Import service here to ensure app context is active
        from section_triple_association_service import SectionTripleAssociationService
        
        # Create service and process document
        service = SectionTripleAssociationService()
        result = service.process_document_section_triple_associations(
            document_id=document_id,
            triple_types=triple_types,
            threshold=threshold
        )
        
        if result.get('success'):
            logger.info(f"Successfully processed document {document_id}")
            logger.info(f"Created {result.get('total_associations')} triple associations across {result.get('sections_processed')} sections")
            
            # Log breakdown by section type if available
            if 'sections' in result:
                for section_id, data in result['sections'].items():
                    if 'associations_by_type' in data:
                        logger.info(f"Section {section_id}: {sum(data['associations_by_type'].values())} associations")
                        for t, count in data['associations_by_type'].items():
                            logger.info(f"  - {t}: {count}")
            
            return True
        else:
            logger.error(f"Error processing document: {result.get('error')}")
            return False
        
    except Exception as e:
        logger.exception(f"Error associating triples with document: {str(e)}")
        return False

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Associate RDF triples with document sections")
    parser.add_argument("document_id", type=int, help="Document ID to process")
    parser.add_argument("--triple-types", type=str, nargs="+", 
                        choices=["Role", "Principle", "Obligation", "Condition", 
                                "Resource", "Action", "Event", "Capability"],
                        help="Types of triples to associate (default: all types)")
    parser.add_argument("--threshold", type=float, default=0.6,
                        help="Minimum similarity threshold (0.0-1.0, default: 0.6)")
    parser.add_argument("--force", action="store_true",
                        help="Force regeneration even if document already has triple associations")
    
    return parser.parse_args()

def main():
    """Main entry point."""
    # Load environment variables
    load_dotenv()
    
    # Parse command line arguments
    args = parse_args()
    
    logger.info(f"Starting triple association for document {args.document_id}")
    logger.info(f"Triple types: {args.triple_types or 'all'}")
    logger.info(f"Similarity threshold: {args.threshold}")
    logger.info(f"Force mode: {args.force}")
    
    # Create app context
    with create_app_context():
        # Get document info
        doc_info = get_document_info(args.document_id)
        if not doc_info:
            sys.exit(1)
            
        logger.info(f"Processing document: {doc_info['title']} (ID: {doc_info['id']})")
        
        # Check if document has sections
        if not doc_info['has_sections']:
            logger.error(f"Document {args.document_id} has no sections. Please generate embeddings first.")
            sys.exit(1)
        
        # Process document
        if associate_triples_with_document(
            document_id=args.document_id,
            triple_types=args.triple_types,
            threshold=args.threshold,
            force=args.force
        ):
            logger.info(f"Successfully associated triples with document {args.document_id}")
        else:
            logger.error(f"Failed to associate triples with document {args.document_id}")
            sys.exit(1)

if __name__ == "__main__":
    main()
