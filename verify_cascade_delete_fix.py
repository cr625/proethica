#!/usr/bin/env python
"""
Script to verify that the cascade delete relationship fix works properly.
This script:
1. Checks if a test document exists
2. Creates a new test document with sections if needed
3. Attempts to delete the document
4. Verifies no orphaned sections remain

Usage:
    python verify_cascade_delete_fix.py
"""

import sys
import os
import logging
from datetime import datetime
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')

def create_test_document(conn):
    """Create a test document with sections for testing cascade delete."""
    
    now = datetime.utcnow()
    title = f"Cascade Delete Test - {now.strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Create document
    insert_doc_query = text("""
        INSERT INTO documents (
            title, document_type, world_id, content, source, file_type, 
            processing_status, doc_metadata, created_at, updated_at
        ) VALUES (
            :title, 'case_study', 1, 'Test content for cascade delete', 
            'verify_cascade_delete.py', 'text', 'completed',
            '{"test": true, "created_for": "cascade_delete_test"}', :now, :now
        ) RETURNING id
    """)
    
    result = conn.execute(insert_doc_query, {"title": title, "now": now})
    document_id = result.scalar()
    conn.commit()
    
    logger.info(f"Created test document with ID {document_id}")
    
    # Create sections
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
        
        conn.execute(insert_section_query, {
            "document_id": document_id,
            "section_id": section["section_id"],
            "section_type": section["section_type"],
            "content": section["content"],
            "now": now
        })
        
        logger.info(f"Created section '{section['section_id']}' for document {document_id}")
    
    conn.commit()
    
    # Verify sections were created
    verify_query = text("""
        SELECT COUNT(*) FROM document_sections WHERE document_id = :document_id
    """)
    section_count = conn.execute(verify_query, {"document_id": document_id}).scalar()
    
    logger.info(f"Verified {section_count} sections for document {document_id}")
    return document_id

def try_database_delete(document_id, conn):
    """Test deleting document directly using SQL."""
    
    # Get document info
    doc_query = text("SELECT title FROM documents WHERE id = :id")
    doc = conn.execute(doc_query, {"id": document_id}).fetchone()
    
    if not doc:
        logger.error(f"Document {document_id} not found")
        return False
    
    logger.info(f"Found document {document_id}: {doc.title}")
    
    # Count sections
    section_query = text("SELECT COUNT(*) FROM document_sections WHERE document_id = :id")
    section_count = conn.execute(section_query, {"id": document_id}).scalar()
    
    logger.info(f"Document {document_id} has {section_count} sections")
    
    # Delete the document
    logger.info(f"Deleting document {document_id}")
    delete_query = text("DELETE FROM documents WHERE id = :id")
    conn.execute(delete_query, {"id": document_id})
    conn.commit()
    
    # Verify document was deleted
    check_query = text("SELECT COUNT(*) FROM documents WHERE id = :id")
    doc_count = conn.execute(check_query, {"id": document_id}).scalar()
    
    if doc_count > 0:
        logger.error(f"Document {document_id} still exists after deletion")
        return False
    
    logger.info(f"Document {document_id} was successfully deleted")
    
    # Check for orphaned sections
    orphan_query = text("SELECT COUNT(*) FROM document_sections WHERE document_id = :id")
    orphan_count = conn.execute(orphan_query, {"id": document_id}).scalar()
    
    if orphan_count > 0:
        logger.error(f"Found {orphan_count} orphaned sections for document {document_id}")
        return False
    
    logger.info("No orphaned sections found - cascade delete worked correctly")
    return True

def check_for_all_orphaned_sections(conn):
    """Check for any orphaned sections in the entire database."""
    
    orphan_query = text("""
        SELECT ds.id, ds.document_id, ds.section_id, ds.section_type
        FROM document_sections ds
        LEFT JOIN documents d ON ds.document_id = d.id
        WHERE d.id IS NULL
    """)
    
    orphans = conn.execute(orphan_query).fetchall()
    
    if orphans:
        logger.warning(f"Found {len(orphans)} orphaned sections in the database")
        for orphan in orphans:
            logger.warning(f"  Orphaned section {orphan.id}: document_id={orphan.document_id}, "
                          f"section_id={orphan.section_id}, type={orphan.section_type}")
        return False
    
    logger.info("No orphaned sections found in the database")
    return True

def main():
    """Main function to test cascade delete."""
    try:
        engine = create_engine(db_url)
        conn = engine.connect()
        
        # Create a test document
        document_id = create_test_document(conn)
        
        # Test deleting the document
        delete_success = try_database_delete(document_id, conn)
        
        # Check for any orphaned sections in the database
        orphan_check = check_for_all_orphaned_sections(conn)
        
        conn.close()
        
        if delete_success and orphan_check:
            logger.info("✅ SUCCESS: Cascade delete is working correctly! The fix was successful.")
            return 0
        else:
            logger.error("❌ FAILED: Cascade delete is not working correctly")
            return 1
    
    except Exception as e:
        logger.exception(f"Error during test: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
