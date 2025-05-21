#!/usr/bin/env python
"""
Test script to verify that the cascade delete relationship works properly.

This script:
1. Creates a test document
2. Adds test document sections to it
3. Attempts to delete the document using the ORM (which should cascade to sections)
4. Verifies that the document and all sections were deleted properly

Usage:
    python test_cascade_delete.py
"""

import sys
import os
import logging
from datetime import datetime
from app import db, create_app
from app.models.document import Document
from app.models.document_section import DocumentSection

# Set database URL
os.environ['DATABASE_URL'] = "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def create_test_document():
    """Create a test document with sections for deletion testing."""
    # Create a test document
    document = Document(
        title="Test Document for Cascade Delete",
        document_type="case_study",
        world_id=1,  # Default world ID
        content="This is a test document for cascade delete testing.",
        source="test_cascade_delete.py",
        file_type="text",
        processing_status="completed",
        doc_metadata={
            "test": True,
            "created_by": "test_cascade_delete.py"
        }
    )
    
    # Save document to get an ID
    db.session.add(document)
    db.session.flush()
    
    document_id = document.id
    logger.info(f"Created test document with ID {document_id}")
    
    # Create test sections
    sections = [
        DocumentSection(
            document_id=document_id,
            section_id="facts",
            section_type="facts",
            content=f"Test facts section for document {document_id}",
            section_metadata={"test": True}
        ),
        DocumentSection(
            document_id=document_id,
            section_id="discussion",
            section_type="discussion",
            content=f"Test discussion section for document {document_id}",
            section_metadata={"test": True}
        ),
        DocumentSection(
            document_id=document_id,
            section_id="conclusion",
            section_type="conclusion",
            content=f"Test conclusion section for document {document_id}",
            section_metadata={"test": True}
        )
    ]
    
    # Add sections to database
    db.session.add_all(sections)
    db.session.commit()
    
    logger.info(f"Created {len(sections)} test sections for document {document_id}")
    return document_id

def test_delete_document(document_id):
    """Test deleting a document with sections using ORM cascade."""
    # Get the document
    document = Document.query.get(document_id)
    if not document:
        logger.error(f"Document {document_id} not found")
        return False
    
    logger.info(f"Found document {document_id}: {document.title}")
    
    # Get section count
    section_count = len(document.document_sections)
    logger.info(f"Document {document_id} has {section_count} sections")
    
    # Delete the document (should cascade to sections)
    db.session.delete(document)
    db.session.commit()
    logger.info(f"Deleted document {document_id}")
    
    # Check if document was deleted
    deleted_document = Document.query.get(document_id)
    if deleted_document:
        logger.error(f"Document {document_id} still exists after deletion")
        return False
    
    # Check if sections were deleted
    sections = DocumentSection.query.filter_by(document_id=document_id).all()
    if sections:
        logger.error(f"Found {len(sections)} sections still existing after document deletion")
        return False
    
    logger.info(f"Successfully deleted document {document_id} and all its sections")
    return True

def main():
    """Main test function."""
    app = create_app()
    
    with app.app_context():
        try:
            # Create test document with sections
            document_id = create_test_document()
            
            # Test deletion with cascade
            success = test_delete_document(document_id)
            
            if success:
                logger.info("CASCADE DELETE TEST PASSED!")
                return 0
            else:
                logger.error("CASCADE DELETE TEST FAILED!")
                return 1
                
        except Exception as e:
            logger.exception(f"Error during test: {str(e)}")
            return 1

if __name__ == "__main__":
    sys.exit(main())
