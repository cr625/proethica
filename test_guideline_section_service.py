"""
Test script for GuidelineSectionService.
Tests the functionality of guideline association with document sections.
"""

import os
import logging
import sys

# Set environment variables BEFORE importing Flask app
os.environ['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
os.environ['DATABASE_URL'] = "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
os.environ['FLASK_ENV'] = "development"

from app import create_app, db
from app.models.document import Document
from app.models.document_section import DocumentSection
from app.services.guideline_section_service import GuidelineSectionService

# Configure logging to display test progress
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

logger = logging.getLogger(__name__)

def test_guideline_section_service():
    """
    Test the GuidelineSectionService functionality.
    This test requires an existing document with sections in the database.
    """
    # Create app with proper database configuration
    app = create_app('config')
    
    # Print current configuration for debugging
    logger.info(f"SQLALCHEMY_DATABASE_URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
    with app.app_context():
        logger.info("Starting GuidelineSectionService test")
        
        # Find a document with sections to test with
        document = Document.query.filter(
            Document.document_type.in_(['case', 'case_study'])
        ).order_by(Document.id.desc()).first()
        
        if not document:
            logger.error("No suitable test document found")
            return
        
        logger.info(f"Using document for testing: ID={document.id}, Title={document.title}")
        
        # Check if document has sections in DocumentSection table
        sections = DocumentSection.query.filter_by(document_id=document.id).all()
        if not sections:
            logger.warning(f"Document {document.id} has no sections in DocumentSection table")
            
            # Check if document has section information in metadata
            if document.doc_metadata and isinstance(document.doc_metadata, dict):
                if 'document_structure' in document.doc_metadata:
                    if 'sections' in document.doc_metadata['document_structure']:
                        section_count = len(document.doc_metadata['document_structure']['sections'])
                        logger.info(f"Document has {section_count} sections in metadata, but not in DocumentSection table")
            
            logger.error("Cannot test GuidelineSectionService without document sections")
            return
        
        logger.info(f"Document has {len(sections)} sections in DocumentSection table")
        
        # Create the service
        service = GuidelineSectionService()
        
        # 1. Test associating guidelines with sections
        logger.info("Testing associate_guidelines_with_sections")
        result = service.associate_guidelines_with_sections(document.id)
        logger.info(f"Association result: {result}")
        
        if not result.get('success', False):
            logger.error(f"Failed to associate guidelines: {result.get('error', 'Unknown error')}")
            return
            
        # Ensure we have a fresh database session and commit
        db.session.commit()
        
        # 2. Test getting guidelines for a specific section
        section = sections[0]
        logger.info(f"Testing get_section_guidelines with section {section.section_type}")
        section_result = service.get_section_guidelines(section.id)
        logger.info(f"Section guidelines result: {section_result}")
        
        # 3. Reload the document to ensure we get the latest metadata
        document = Document.query.get(document.id)
        logger.info(f"Reloaded document metadata: {document.doc_metadata != None}")
        
        # 4. Test getting all section guidelines for the document
        logger.info(f"Testing get_document_section_guidelines with document {document.id}")
        document_result = service.get_document_section_guidelines(document.id)
        logger.info(f"Document section guidelines result: {document_result}")
        
        logger.info("GuidelineSectionService test completed")

if __name__ == "__main__":
    test_guideline_section_service()
