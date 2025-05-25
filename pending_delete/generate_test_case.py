#!/usr/bin/env python
"""
Script to generate a test case with document sections for testing cascade delete.

This script:
1. Creates a new document with the specified title
2. Adds standard document sections to it
3. Returns the document ID for testing

Usage:
    python generate_test_case.py "Test Case Title"
"""

import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
import os
import argparse
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')

def generate_test_case(title, engine):
    """Generate a test case with document sections."""
    
    # Create a session
    Session = scoped_session(sessionmaker(bind=engine))
    session = Session()
    
    try:
        # First create the document
        now = datetime.utcnow()
        insert_doc_query = text("""
            INSERT INTO documents (
                title, document_type, world_id, content, source, file_type,
                processing_status, doc_metadata, created_at, updated_at
            ) VALUES (
                :title, 'case_study', 1, 'Test content for cascade delete test', 
                'generate_test_case.py', 'text', 'completed', 
                '{"test": true, "created_for": "cascade_delete_test"}', :now, :now
            ) RETURNING id
        """)
        
        result = session.execute(insert_doc_query, {"title": title, "now": now})
        document_id = result.scalar()
        
        logger.info(f"Created test document with ID {document_id}")
        
        # Now create sections for this document
        sections = [
            {"section_id": "facts", "section_type": "facts", 
             "content": "Test facts content for cascade delete test"},
            {"section_id": "discussion", "section_type": "discussion", 
             "content": "Test discussion content for cascade delete test"},
            {"section_id": "conclusion", "section_type": "conclusion", 
             "content": "Test conclusion content for cascade delete test"}
        ]
        
        for section in sections:
            insert_section_query = text("""
                INSERT INTO document_sections (
                    document_id, section_id, section_type, content, 
                    section_metadata, created_at, updated_at
                ) VALUES (
                    :document_id, :section_id, :section_type, :content,
                    '{"test": true}', :now, :now
                )
            """)
            
            session.execute(insert_section_query, {
                "document_id": document_id,
                "section_id": section["section_id"],
                "section_type": section["section_type"],
                "content": section["content"],
                "now": now
            })
            
            logger.info(f"Created section '{section['section_id']}' for document {document_id}")
        
        # Commit the transaction
        session.commit()
        logger.info(f"Successfully created test case {document_id} with sections")
        
        # Verify sections were created
        verify_query = text("""
            SELECT COUNT(*) FROM document_sections WHERE document_id = :document_id
        """)
        count = session.execute(verify_query, {"document_id": document_id}).scalar()
        
        logger.info(f"Verified {count} sections for document {document_id}")
        return document_id
    
    except Exception as e:
        session.rollback()
        logger.exception(f"Error generating test case: {str(e)}")
        return None
    
    finally:
        session.close()

def main():
    """Main function."""
    # Parse arguments
    parser = argparse.ArgumentParser(description='Generate a test case with document sections')
    parser.add_argument('title', type=str, help='Title for the test case')
    args = parser.parse_args()
    
    # Create engine
    engine = create_engine(db_url)
    
    # Generate test case
    document_id = generate_test_case(args.title, engine)
    
    if document_id:
        print(f"TEST_CASE_ID={document_id}")
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())
