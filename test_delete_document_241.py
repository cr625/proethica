#!/usr/bin/env python
"""
Script to test the cascade deletion of a document with sections using the SQLAlchemy ORM.
This tests that our fix in the DocumentSection model works properly.

Usage:
    python test_delete_document_241.py
"""

import sys
import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
from app import db, create_app
from app.models.document import Document
from app.models.document_section import DocumentSection

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set database URL
os.environ['DATABASE_URL'] = "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
os.environ['SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"

def test_delete_via_orm():
    """Test deleting document 241 via the ORM to test cascade delete."""
    app = create_app()
    
    with app.app_context():
        try:
            # Get document 241
            document = Document.query.get(241)
            
            if not document:
                logger.error("Document 241 not found")
                return False
            
            logger.info(f"Found document 241: {document.title}")
            
            # Count sections
            section_count = len(document.document_sections)
            if section_count == 0:
                logger.warning(f"Document 241 has no sections")
            else:
                logger.info(f"Document 240 has {section_count} sections")
                # List each section
                for i, section in enumerate(document.document_sections):
                    logger.info(f"  - Section {i+1}: {section.section_id} ({section.section_type})")
            
            # Delete the document (should cascade to sections if our fix works)
            logger.info("Deleting document...")
            db.session.delete(document)
            db.session.commit()
            logger.info("Document deleted")
            
            # Verify document was deleted
            check_document = Document.query.get(241)
            if check_document:
                logger.error("Document 241 still exists after deletion")
                return False
            logger.info("Document 241 was successfully deleted")
            
            # Verify sections were deleted
            sections = DocumentSection.query.filter_by(document_id=241).all()
            if sections:
                logger.error(f"Found {len(sections)} sections still existing after document deletion")
                for section in sections:
                    logger.error(f"  Orphaned section: {section.id} - {section.section_id}")
                return False
            logger.info("All document sections were successfully deleted")
            
            return True
        
        except Exception as e:
            logger.exception(f"Error during cascade delete test: {str(e)}")
            db.session.rollback()
            return False

def check_via_raw_sql():
    """Double-check using raw SQL that everything was deleted properly."""
    # Create a direct database connection
    engine = create_engine(os.environ['DATABASE_URL'])
    conn = engine.connect()
    
    try:
        # Check if document exists
        doc_query = text("SELECT * FROM documents WHERE id = 241")
        doc_result = conn.execute(doc_query).fetchone()
        
        if doc_result:
            logger.error("Document 241 still exists in the database (raw SQL check)")
            return False
        logger.info("Verified document 241 does not exist (raw SQL check)")
        
        # Check if any sections exist
        section_query = text("SELECT * FROM document_sections WHERE document_id = 241")
        section_result = conn.execute(section_query).fetchall()
        
        if section_result:
            logger.error(f"Found {len(section_result)} orphaned sections (raw SQL check)")
            return False
        logger.info("Verified no orphaned document sections exist (raw SQL check)")
        
        return True
    
    finally:
        conn.close()

def main():
    """Main function to run the test."""
    logger.info("Testing cascade delete for Case 241...")
    
    # Test via ORM
    orm_success = test_delete_via_orm()
    
    # Double-check via raw SQL
    sql_success = check_via_raw_sql()
    
    if orm_success and sql_success:
        logger.info("CASCADE DELETE TEST PASSED! ✅")
        logger.info("Model relationship correctly set up with cascade='all, delete-orphan'")
        return 0
    else:
        logger.error("CASCADE DELETE TEST FAILED! ❌")
        logger.error("Reason: Cascading delete not working properly")
        return 1

if __name__ == "__main__":
    sys.exit(main())
