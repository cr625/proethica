#!/usr/bin/env python
"""
Modified script to batch update section embeddings for all cases.
This version uses the application context from the running app.
"""
import os
import sys
import time
import logging
from datetime import datetime
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"section_embeddings_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
if os.path.exists('.env'):
    load_dotenv()
    logger.info("Loaded environment from .env file")

# Ensure the SQLALCHEMY_DATABASE_URI is set from DATABASE_URL
if 'DATABASE_URL' in os.environ and 'SQLALCHEMY_DATABASE_URI' not in os.environ:
    os.environ['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
    logger.info(f"Set SQLALCHEMY_DATABASE_URI from DATABASE_URL: {os.environ['DATABASE_URL']}")

def main():
    """Process all cases with document structure."""
    # Import dependencies inside function to ensure app config is loaded
    from app import create_app
    from app.services.section_embedding_service import SectionEmbeddingService
    from app.models.document import Document
    from sqlalchemy import text
    from app import db
    
    # Create app with config module - matching how run.py initializes the app
    app = create_app('config')
    
    # Double check database configuration
    if not app.config.get('SQLALCHEMY_DATABASE_URI') and 'SQLALCHEMY_DATABASE_URI' in os.environ:
        app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['SQLALCHEMY_DATABASE_URI']
        logger.info(f"Explicitly set database URI in app config: {os.environ['SQLALCHEMY_DATABASE_URI']}")
    
    with app.app_context():
        logger.info("Starting batch section embedding generation")
        
        # Initialize the section embedding service
        section_embedding_service = SectionEmbeddingService()
        
        # Find all documents with document structure
        try:
            # Query for documents with document_structure in metadata
            query = text("SELECT id FROM documents WHERE doc_metadata IS NOT NULL")
            results = db.session.execute(query)
            
            document_ids = [row.id for row in results]
            logger.info(f"Found {len(document_ids)} documents with metadata")
            
            # Filter to those that actually have document_structure
            case_ids = []
            for doc_id in document_ids:
                doc = Document.query.get(doc_id)
                if doc and doc.doc_metadata and 'document_structure' in doc.doc_metadata:
                    case_ids.append(doc.id)
            
            logger.info(f"Found {len(case_ids)} cases with document structure")
            
            # Skip case 252 since you already did it
            if 252 in case_ids:
                case_ids.remove(252)
                logger.info("Skipping case 252 (already processed)")
            
            # Track progress
            successes = 0
            failures = 0
            
            # Process each case
            for i, case_id in enumerate(case_ids):
                try:
                    logger.info(f"Processing case {i+1}/{len(case_ids)}: ID {case_id}")
                    
                    # Process the document sections
                    result = section_embedding_service.process_document_sections(case_id)
                    
                    if result.get('success'):
                        logger.info(f"Successfully processed {result.get('sections_embedded')} sections for case {case_id}")
                        successes += 1
                    else:
                        logger.error(f"Error processing case {case_id}: {result.get('error')}")
                        failures += 1
                        
                    # Add a small delay between cases
                    time.sleep(0.5)
                    
                except Exception as e:
                    logger.exception(f"Exception processing case {case_id}: {str(e)}")
                    failures += 1
            
            logger.info(f"Processing complete: {successes} successes, {failures} failures")
            
        except Exception as e:
            logger.exception(f"Error processing cases: {str(e)}")

if __name__ == "__main__":
    start_time = time.time()
    main()
    elapsed = time.time() - start_time
    logger.info(f"Total execution time: {elapsed:.2f} seconds")
