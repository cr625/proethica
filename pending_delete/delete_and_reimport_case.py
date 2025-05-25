#!/usr/bin/env python3
"""
Delete and Reimport NSPE Case
---------------------------
Deletes the existing case (ID 186) and reimports it using the enhanced
processing pipeline with proper metadata extraction and ontology triple
generation.

This script:
1. Deletes the specified case from the database
2. Reimports it using the improved pipeline
3. Confirms successful import with metadata and ontology triples
"""

import sys
import os
import logging
import argparse
import psycopg2

# Add the NSPE pipeline directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'nspe-pipeline')))

# Import the case processing function
from process_nspe_case import process_case_from_url
from utils.database import get_case

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("delete_and_reimport")

# Database connection parameters
DB_NAME = "ai_ethical_dm"
DB_USER = "postgres"
DB_PASSWORD = "PASS"  # Replace with actual password if needed
DB_HOST = "localhost"
DB_PORT = "5433"      # PostgreSQL port used in Docker

def get_connection():
    """Get a PostgreSQL database connection."""
    try:
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {str(e)}")
        return None

def delete_case(case_id):
    """
    Delete a case from the database.
    
    Args:
        case_id: ID of the case to delete
        
    Returns:
        bool: True if successful, False otherwise
    """
    logger.info(f"Deleting case with ID {case_id} from database")
    
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # Delete the case's entity triples first
        cursor.execute("""
            DELETE FROM entity_triples 
            WHERE entity_type = 'document' AND temporal_region_type = %s
        """, (str(case_id),))
        triples_deleted = cursor.rowcount
        logger.info(f"Deleted {triples_deleted} entity triples")
        
        # Delete the document
        cursor.execute("DELETE FROM documents WHERE id = %s", (case_id,))
        doc_deleted = cursor.rowcount
        
        # Commit the transaction
        conn.commit()
        cursor.close()
        conn.close()
        
        if doc_deleted > 0:
            logger.info(f"Successfully deleted case {case_id}")
            return True
        else:
            logger.warning(f"No case with ID {case_id} found")
            return False
            
    except Exception as e:
        logger.error(f"Error deleting case {case_id}: {str(e)}")
        conn.rollback()
        conn.close()
        return False

def reimport_case(url):
    """
    Reimport a case using the enhanced pipeline.
    
    Args:
        url: URL of the case to import
        
    Returns:
        dict: Result of the import operation
    """
    logger.info(f"Reimporting case from URL: {url}")
    
    # Process the case with the enhanced pipeline
    result = process_case_from_url(
        url, 
        clear_existing_triples=True,
        integrate_with_world=True,
        add_mclaren_triples=True
    )
    
    if result['success']:
        case_id = result['case_id']
        logger.info(f"Successfully reimported case: {result['title']} (ID: {case_id})")
        
        # Fetch the complete case with all associated data
        complete_case = get_case(case_id=case_id)
        
        # Display case details
        print("\n" + "="*80)
        print(f"REIMPORTED CASE: {complete_case.get('title')} (ID: {case_id})")
        print(f"Case Number: {complete_case.get('doc_metadata', {}).get('case_number')}")
        print(f"Year: {complete_case.get('doc_metadata', {}).get('year')}")
        print("="*80)
        
        # Display ontology triples info
        if result.get('ontology', {}).get('success', False):
            eng_count = result['ontology'].get('eng_triple_count', 0)
            mclaren_count = result['ontology'].get('mclaren_triple_count', 0)
            total_count = result['ontology'].get('total_triple_count', 0)
            
            print("\n=== ONTOLOGY TRIPLES ADDED ===")
            print(f"Engineering Ethics: {eng_count} triples")
            print(f"McLaren Extensional: {mclaren_count} triples")
            print(f"Total: {total_count} triples")
        else:
            print("\nNo ontology triples were added.")
        
        # Display case viewing URL
        print("\nCase can be viewed at:")
        print(f"http://localhost:3333/cases/{case_id}\n")
        
    return result

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description='Delete and reimport an NSPE case')
    parser.add_argument('--case-id', type=int, default=186,
                       help='ID of the case to delete (default: 186)')
    parser.add_argument('--url', default='https://www.nspe.org/career-growth/ethics/board-ethical-review-cases/acknowledging-errors-design',
                       help='URL of the case to reimport (default: Acknowledging Errors in Design)')
    parser.add_argument('--skip-delete', action='store_true',
                       help='Skip deletion and only reimport the case')
    args = parser.parse_args()
    
    # Delete the case first (unless skipped)
    if not args.skip_delete:
        delete_success = delete_case(args.case_id)
        if not delete_success and not args.skip_delete:
            logger.error(f"Failed to delete case {args.case_id}")
            return 1
    
    # Reimport the case
    result = reimport_case(args.url)
    
    if result['success']:
        print(f"\nSuccessfully reimported case with new ID: {result['case_id']}")
        return 0
    else:
        logger.error(f"Failed to reimport case: {result['message']}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
