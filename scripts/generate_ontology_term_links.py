#!/usr/bin/env python3
"""
Generate Ontology Term Links

Batch script to process existing documents and generate ontology term links
for all sections. This identifies individual words/phrases that match terms
in the engineering-ethics ontology.

Usage:
    python scripts/generate_ontology_term_links.py [options]

Options:
    --document-id ID    Process only the specified document ID
    --force             Force regeneration of existing term links
    --limit N           Limit processing to N documents
    --world-id ID       Process only documents from specified world
    --dry-run           Show what would be processed without making changes
"""

import sys
import os
import argparse
import logging
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
if os.path.exists('.env'):
    load_dotenv()

# Set environment for development
os.environ.setdefault('ENVIRONMENT', 'development')

# Set database URL if not already set
if not os.environ.get('SQLALCHEMY_DATABASE_URI'):
    db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    os.environ['SQLALCHEMY_DATABASE_URI'] = db_url

from app import create_app, db
from app.models.document import Document
from app.models.section_term_link import SectionTermLink
from app.services.ontology_term_recognition_service import OntologyTermRecognitionService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('ontology_term_links.log')
    ]
)
logger = logging.getLogger(__name__)

def main():
    """Main function to process documents and generate term links."""
    parser = argparse.ArgumentParser(description='Generate ontology term links for document sections')
    parser.add_argument('--document-id', type=int, help='Process only the specified document ID')
    parser.add_argument('--force', action='store_true', help='Force regeneration of existing term links')
    parser.add_argument('--limit', type=int, help='Limit processing to N documents')
    parser.add_argument('--world-id', type=int, help='Process only documents from specified world')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without making changes')
    
    args = parser.parse_args()
    
    # Create Flask app
    app = create_app('config')
    
    with app.app_context():
        try:
            # Initialize the term recognition service
            logger.info("Initializing ontology term recognition service...")
            recognition_service = OntologyTermRecognitionService()
            
            if not recognition_service.ontology_terms:
                logger.error("No ontology terms loaded. Cannot proceed with term recognition.")
                return 1
            
            logger.info(f"Loaded {len(recognition_service.ontology_terms)} ontology terms for matching")
            
            # Build query for documents to process
            query = Document.query.filter(Document.document_type.in_(['case', 'case_study']))
            
            if args.document_id:
                query = query.filter(Document.id == args.document_id)
                logger.info(f"Processing single document ID: {args.document_id}")
            elif args.world_id:
                query = query.filter(Document.world_id == args.world_id)
                logger.info(f"Processing documents from world ID: {args.world_id}")
            
            if args.limit:
                query = query.limit(args.limit)
                logger.info(f"Limiting processing to {args.limit} documents")
            
            # Get documents to process
            documents = query.all()
            
            if not documents:
                logger.warning("No documents found to process")
                return 0
            
            logger.info(f"Found {len(documents)} documents to process")
            
            # Process each document
            total_processed = 0
            total_links_created = 0
            total_errors = 0
            
            for document in documents:
                try:
                    logger.info(f"Processing document {document.id}: {document.title}")
                    
                    # Check if term links already exist
                    existing_links = SectionTermLink.query.filter_by(document_id=document.id).count()
                    
                    if existing_links > 0 and not args.force:
                        logger.info(f"Document {document.id} already has {existing_links} term links (use --force to regenerate)")
                        continue
                    
                    if args.dry_run:
                        logger.info(f"DRY RUN: Would process document {document.id} ({existing_links} existing links)")
                        total_processed += 1
                        continue
                    
                    # Process the document
                    result = recognition_service.process_document_sections(
                        document.id, 
                        force_regenerate=args.force
                    )
                    
                    if result.get('success'):
                        links_created = result.get('term_links_created', 0)
                        sections_processed = result.get('sections_processed', 0)
                        
                        logger.info(f"Successfully processed document {document.id}: "
                                  f"{links_created} term links created across {sections_processed} sections")
                        
                        total_processed += 1
                        total_links_created += links_created
                    else:
                        error_msg = result.get('error', 'Unknown error')
                        logger.error(f"Failed to process document {document.id}: {error_msg}")
                        total_errors += 1
                
                except Exception as e:
                    logger.exception(f"Exception processing document {document.id}: {str(e)}")
                    total_errors += 1
                    continue
            
            # Summary
            logger.info("=" * 60)
            logger.info("PROCESSING SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Documents processed: {total_processed}")
            logger.info(f"Total term links created: {total_links_created}")
            logger.info(f"Errors encountered: {total_errors}")
            
            if args.dry_run:
                logger.info("DRY RUN - No changes were made to the database")
            
            return 0 if total_errors == 0 else 1
            
        except Exception as e:
            logger.exception(f"Fatal error in main processing: {str(e)}")
            return 1

if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)