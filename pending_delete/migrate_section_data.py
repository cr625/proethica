"""
Migration script to migrate existing section data from document.doc_metadata
to the new DocumentSection model with pgvector support.
"""

import os
import sys
import logging
import json
from datetime import datetime
from flask import Flask
import time

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the parent directory to the path so we can import from app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

def create_app():
    """Create and configure the Flask app."""
    app = Flask(__name__)
    app.config.from_object('app.config.DevelopmentConfig')
    # Don't import all routes to avoid model relation issues
    return app

def run_migration():
    """Run the migration to migrate section data to DocumentSection model."""
    # First, we need to run the migration to create the document_sections table
    logger.info("First, running migration to create document_sections table if it doesn't exist")
    try:
        import migration_document_sections
        migration_document_sections.run_migration()
    except Exception as e:
        logger.error(f"Error running migration_document_sections: {str(e)}")
        return
    
    # Import the mock User model first to satisfy dependencies
    from app.models.mock_user import User
    
    # Now import the necessary models and services
    from app import db
    from app.models.document import Document
    from app.models.document_section import DocumentSection
    from app.services.section_embedding_service import SectionEmbeddingService
    
    # Create Flask app and set up context
    app = create_app()
    with app.app_context():
        try:
            # Find all documents that might have section embeddings
            documents = Document.query.all()
            logger.info(f"Found {len(documents)} documents to check for section embeddings")
            
            # Initialize SectionEmbeddingService
            section_service = SectionEmbeddingService()
            
            migrated_count = 0
            skipped_count = 0
            
            for document in documents:
                doc_id = document.id
                logger.info(f"Processing document {doc_id}: {document.title}")
                
                # Check if document has metadata
                if not document.doc_metadata:
                    logger.info(f"Document {doc_id} has no metadata, skipping")
                    skipped_count += 1
                    continue
                
                # Get document metadata
                doc_metadata = document.doc_metadata
                
                # Check if document has structure data
                has_structure = False
                section_embeddings_exist = False
                
                # Check various possible metadata structures
                if 'document_structure' in doc_metadata:
                    has_structure = True
                    # Check if it has section embeddings
                    if 'section_embeddings' in doc_metadata['document_structure']:
                        section_embeddings_exist = True
                
                # Skip if no structure or embeddings
                if not has_structure:
                    logger.info(f"Document {doc_id} has no document_structure, skipping")
                    skipped_count += 1
                    continue
                
                # Process the document to extract and store section data
                logger.info(f"Migrating section data for document {doc_id}")
                
                # Use the existing process_document_sections method to handle the migration
                result = section_service.process_document_sections(doc_id)
                
                if result['success']:
                    logger.info(f"Successfully migrated sections for document {doc_id}")
                    migrated_count += 1
                else:
                    logger.warning(f"Failed to migrate sections for document {doc_id}: {result.get('error', 'unknown error')}")
                    skipped_count += 1
                
                # Add a short delay to avoid overloading the system
                time.sleep(0.1)
            
            logger.info(f"Migration complete. Migrated {migrated_count} documents, skipped {skipped_count} documents.")
            
            # Verify the migration
            total_sections = DocumentSection.query.count()
            logger.info(f"Total number of document sections in the new table: {total_sections}")
            
        except Exception as e:
            logger.exception(f"Error during section data migration: {str(e)}")
            
if __name__ == '__main__':
    logger.info("Starting section data migration...")
    run_migration()
    logger.info("Migration finished.")
