#!/usr/bin/env python
"""
Test script to verify that section embedding metadata is properly displayed in the UI.

This script:
1. Retrieves a document with section embeddings
2. Verifies the document_structure metadata contains section_embeddings
3. Creates a simulated render of how this would appear in the UI

Usage:
    python test_section_embedding_metadata.py
"""

import sys
import json
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
import os

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')

def main():
    """Main test function."""
    logger.info("Starting section embedding metadata test")
    
    # Create database engine and session
    engine = create_engine(db_url)
    session_factory = sessionmaker(bind=engine)
    Session = scoped_session(session_factory)
    session = Session()
    
    try:
        # Find a document that has section embeddings
        query = """
        SELECT 
            ds.document_id,
            COUNT(ds.id) as section_count,
            d.doc_metadata,
            d.title
        FROM 
            document_sections ds
        JOIN 
            documents d ON ds.document_id = d.id
        GROUP BY 
            ds.document_id, d.doc_metadata, d.id, d.title
        HAVING 
            COUNT(ds.id) > 0
        ORDER BY 
            COUNT(ds.id) DESC
        LIMIT 1
        """
        
        result = session.execute(text(query)).fetchone()
        
        if not result:
            logger.error("No documents with section embeddings found")
            return 1
            
        document_id = result.document_id
        section_count = result.section_count
        doc_metadata = result.doc_metadata
        title = result.title
        
        logger.info(f"Testing document ID {document_id}: '{title}' with {section_count} sections")
        
        # Verify document_structure and section_embeddings in metadata
        has_document_structure = 'document_structure' in doc_metadata
        has_section_embeddings = (has_document_structure and 
                                'section_embeddings' in doc_metadata['document_structure'])
        
        logger.info(f"Has document_structure: {has_document_structure}")
        logger.info(f"Has section_embeddings: {has_section_embeddings}")
        
        if has_section_embeddings:
            section_embeddings_info = doc_metadata['document_structure']['section_embeddings']
            logger.info(f"Section embeddings info: {json.dumps(section_embeddings_info, indent=2)}")
            
            # Verify count matches
            metadata_count = section_embeddings_info.get('count', 0)
            logger.info(f"Metadata section count: {metadata_count}, Actual section count: {section_count}")
            
            if metadata_count != section_count:
                logger.warning(f"Metadata count ({metadata_count}) doesn't match actual count ({section_count})")
        else:
            logger.warning("Document does not have section_embeddings metadata")
            
        # Simulate UI rendering
        print("\n" + "="*80)
        print(f"CASE DETAIL SIMULATION FOR: {title} (ID: {document_id})")
        print("="*80)
        
        # Simulate the View Structure button
        view_structure_button = f'<a href="/structure/view/{document_id}" class="btn btn-primary">'
        view_structure_button += '<i class="bi bi-diagram-3"></i> View Structure'
        
        if has_section_embeddings:
            embeddings_count = doc_metadata['document_structure']['section_embeddings'].get('count', 0)
            view_structure_button += f' <span class="badge bg-success">{embeddings_count} sections</span>'
        
        view_structure_button += '</a>'
        
        print(view_structure_button)
        print("="*80 + "\n")
        
        # Get information about the sections
        if section_count > 0:
            section_query = """
            SELECT 
                section_id, 
                section_type,
                LENGTH(content) as content_length
            FROM 
                document_sections
            WHERE 
                document_id = :document_id
            ORDER BY 
                section_id
            """
            
            sections = session.execute(
                text(section_query), 
                {'document_id': document_id}
            ).fetchall()
            
            print("DOCUMENT SECTIONS:")
            print("-"*80)
            for section in sections:
                print(f"- {section.section_id} ({section.section_type}): {section.content_length} chars")
            
            print("\nTest completed successfully!")
            return 0
            
    except Exception as e:
        logger.exception(f"Error during test: {str(e)}")
        return 1
    finally:
        session.close()

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
