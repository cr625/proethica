#!/usr/bin/env python3
"""
Direct script to import NSPE cases from JSON files into the documents table
without using SQLAlchemy.
"""

import sys
import json
import logging
import traceback
import psycopg2
import psycopg2.extras
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("direct_import_nspe_cases")

# Database connection parameters
DB_PARAMS = {
    "dbname": "ai_ethical_dm",
    "user": "postgres",
    "password": "PASS",
    "host": "localhost",
    "port": "5433"
}

def import_cases():
    """
    Import NSPE cases from JSON files into the documents table
    """
    try:
        # Connect to database
        conn = psycopg2.connect(**DB_PARAMS)
        conn.autocommit = False
        cur = conn.cursor()
        
        logger.info("Connected to database")

        # Load cases from JSON files
        json_files = [
            'data/modern_nspe_cases.json',
            'data/nspe_cases.json'
        ]

        all_cases = []
        for json_file in json_files:
            try:
                with open(json_file, 'r') as f:
                    cases_data = json.load(f)
                    logger.info(f"Loaded {len(cases_data)} cases from {json_file}")
                    all_cases.extend(cases_data)
            except Exception as e:
                logger.error(f"Error loading {json_file}: {str(e)}")

        logger.info(f"Total cases loaded: {len(all_cases)}")

        # For each case in the JSON data
        import_count = 0
        for case in all_cases:
            title = case.get('title', '')
            case_number = case.get('case_number', '')
            year = case.get('year', '')
            full_text = case.get('full_text', '')
            url = case.get('url', '')

            # Skip empty cases
            if not title or not full_text:
                logger.warning(f"Skipping case with missing title or content: {case_number}")
                continue

            # Construct case title if needed
            if not title and case_number:
                title = f"NSPE Case {case_number}"

            # Check if the case already exists in documents table
            cur.execute(
                """
                SELECT id FROM documents
                WHERE external_id = %s
                """, 
                (case_number,)
            )
            existing = cur.fetchone()

            # If case exists, update content
            if existing:
                logger.info(f"Updating existing case: {title}")
                # Update directly with simpler approach - use the entire metadata object
                metadata = {
                    "case_number": case_number,
                    "year": year
                }

                # Add any additional metadata
                if 'metadata' in case and isinstance(case['metadata'], dict):
                    for key, value in case['metadata'].items():
                        metadata[key] = value

                metadata_json = json.dumps(metadata)
                cur.execute(
                    """
                    UPDATE documents
                    SET content = %s,
                        doc_metadata = %s,
                        source_url = %s,
                        updated_at = %s
                    WHERE id = %s
                    """,
                    (full_text, metadata_json, url, datetime.now(), existing[0])
                )
            # Otherwise insert new case
            else:
                logger.info(f"Inserting new case: {title}")
                metadata = {
                    "case_number": case_number,
                    "year": year
                }

                # Add any additional metadata
                if 'metadata' in case and isinstance(case['metadata'], dict):
                    for key, value in case['metadata'].items():
                        metadata[key] = value

                metadata_json = json.dumps(metadata)
                
                # Insert the new document
                cur.execute(
                    """
                    INSERT INTO documents
                    (title, content, doc_type, external_id, source_url, doc_date, doc_metadata, created_at)
                    VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        title, 
                        full_text, 
                        "case", 
                        case_number, 
                        url, 
                        datetime.strptime(str(year), "%Y") if year else None,
                        metadata_json, 
                        datetime.now()
                    )
                )

                new_id = cur.fetchone()[0]
                logger.info(f"Inserted case: {title} with ID {new_id}")

            import_count += 1

            # Commit every 10 cases to avoid long transactions
            if import_count % 10 == 0:
                conn.commit()
                logger.info(f"Committed batch of cases - {import_count} processed so far")

        # Final commit
        conn.commit()
        
        # Close cursor and connection
        cur.close()
        conn.close()

        logger.info(f"Imported/updated {import_count} cases in total")
        return True
    except Exception as e:
        logger.error(f"Error importing cases: {str(e)}")
        traceback.print_exc()
        
        # Rollback and close connections if there's an error
        if 'conn' in locals() and conn:
            conn.rollback()
            
            if 'cur' in locals() and cur:
                cur.close()
            
            conn.close()
            
        return False

if __name__ == "__main__":
    if import_cases():
        logger.info("NSPE case import completed successfully")
        sys.exit(0)
    else:
        logger.error("NSPE case import failed")
        sys.exit(1)
