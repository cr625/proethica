#!/usr/bin/env python
"""
Script to safely delete cases with document sections by handling the deletion
of document_sections first to avoid integrity constraint errors.

Usage:
    python cleanup_cases_with_sections.py 238 239
    
    This will delete cases 238 and 239 along with their document sections.
"""

import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, scoped_session
import os
import argparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')

def delete_case_with_sections(case_id, session, dry_run=False):
    """Delete a case and its associated document sections."""
    
    # First, check if the case exists
    case_exists_query = text("SELECT id, title FROM documents WHERE id = :case_id")
    case = session.execute(case_exists_query, {"case_id": case_id}).fetchone()
    
    if not case:
        logger.warning(f"Case {case_id} does not exist.")
        return False
    
    logger.info(f"Found case {case_id}: {case.title}")
    
    # Check for document sections
    section_query = text("""
        SELECT COUNT(*) 
        FROM document_sections 
        WHERE document_id = :case_id
    """)
    section_count = session.execute(section_query, {"case_id": case_id}).scalar()
    
    logger.info(f"Case {case_id} has {section_count} document sections")
    
    # Display what will happen
    logger.info(f"{'Would delete' if dry_run else 'Deleting'} {section_count} document sections for case {case_id}")
    logger.info(f"{'Would delete' if dry_run else 'Deleting'} case {case_id}: {case.title}")
    
    if dry_run:
        logger.info("DRY RUN: No changes will be made to the database")
        return True
    
    try:
        # Delete document sections first
        if section_count > 0:
            delete_sections_query = text("""
                DELETE FROM document_sections
                WHERE document_id = :case_id
            """)
            result = session.execute(delete_sections_query, {"case_id": case_id})
            logger.info(f"Deleted {result.rowcount} document sections for case {case_id}")
        
        # Delete document chunks (embeddings) to avoid integrity constraints
        delete_chunks_query = text("""
            DELETE FROM document_chunks
            WHERE document_id = :case_id
        """)
        chunk_result = session.execute(delete_chunks_query, {"case_id": case_id})
        if chunk_result.rowcount > 0:
            logger.info(f"Deleted {chunk_result.rowcount} document chunks for case {case_id}")
        
        # Finally, delete the document itself
        delete_document_query = text("""
            DELETE FROM documents
            WHERE id = :case_id
        """)
        doc_result = session.execute(delete_document_query, {"case_id": case_id})
        
        if doc_result.rowcount > 0:
            logger.info(f"Successfully deleted case {case_id}")
            return True
        else:
            logger.error(f"Failed to delete case {case_id} (possibly due to other constraints)")
            return False
    
    except Exception as e:
        logger.exception(f"Error while deleting case {case_id}: {str(e)}")
        return False

def main():
    """Main function to delete cases with their document sections."""
    
    # Set up argument parser
    parser = argparse.ArgumentParser(description='Delete cases with their document sections')
    parser.add_argument('case_ids', metavar='case_id', type=int, nargs='+',
                        help='IDs of cases to delete')
    parser.add_argument('--dry-run', action='store_true',
                        help='Run without making any changes to the database')
    
    args = parser.parse_args()
    case_ids = args.case_ids
    dry_run = args.dry_run
    
    if not case_ids:
        logger.error("No case IDs provided.")
        return 1
    
    logger.info(f"Preparing to {'test delete' if dry_run else 'delete'} {len(case_ids)} cases: {', '.join(map(str, case_ids))}")
    
    # Create database engine and session
    engine = create_engine(db_url)
    session_factory = sessionmaker(bind=engine)
    Session = scoped_session(session_factory)
    session = Session()
    
    success_count = 0
    failure_count = 0
    
    try:
        for case_id in case_ids:
            if delete_case_with_sections(case_id, session, dry_run):
                success_count += 1
            else:
                failure_count += 1
        
        if not dry_run:
            # Commit the transaction
            session.commit()
            logger.info("All deletions committed successfully")
        else:
            logger.info("DRY RUN - No changes made to the database")
            session.rollback()
    
    except Exception as e:
        # Rollback the transaction on error
        session.rollback()
        logger.exception(f"Error during case deletion: {str(e)}")
        return 1
    
    finally:
        # Close the session
        session.close()
    
    # Log summary
    logger.info(f"Deletion {'test' if dry_run else 'operation'} complete:")
    logger.info(f"  - {success_count} cases {'would be' if dry_run else 'were'} processed successfully")
    logger.info(f"  - {failure_count} cases {'would have' if dry_run else 'had'} errors")
    
    return 0 if failure_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
