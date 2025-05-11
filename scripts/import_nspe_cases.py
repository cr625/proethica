#!/usr/bin/env python3
"""
Script to import NSPE cases from JSON files into the documents table.
"""

import sys
import json
import logging
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("import_nspe_cases")

def import_cases():
    """
    Import NSPE cases from JSON files into the documents table
    """
    try:
        # Connect to database
        engine = create_engine(
            "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
        )
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
        
        with engine.connect() as conn:
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
                existing = conn.execute(text(
                    """
                    SELECT id FROM documents 
                    WHERE title = :title AND document_type = 'case_study'
                    """
                ), {"title": title}).fetchone()
                
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
                    conn.execute(text(
                        """
                        UPDATE documents
                        SET content = :content,
                            doc_metadata = CAST(:metadata AS jsonb),
                            source = :url
                        WHERE id = :id
                        """
                    ), {
                        "content": full_text,
                        "metadata": metadata_json,
                        "url": url,
                        "id": existing[0]
                    })
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
                    
                    # Use a simple approach - let psycopg2 handle the JSON/JSONB conversion
                    # Create a direct SQL query that doesn't use any PostgreSQL-specific casting
                    result = conn.execute(text(
                        """
                        INSERT INTO documents
                        (title, content, document_type, world_id, doc_metadata,
                         processing_status, processing_progress, source, created_at, updated_at)
                        VALUES
                        (:title, :content, 'case_study', 1, NULL,
                         'completed', 100, :url, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        RETURNING id
                        """
                    ), {
                        "title": title,
                        "content": full_text,
                        "url": url
                    })
                    
                    # Get the new ID
                    new_id = result.fetchone()[0]
                    
                    # Then update the metadata separately with a simpler query using string concatenation
                    # instead of PostgreSQL-specific cast operators
                    metadata_json = json.dumps(metadata)
                    conn.execute(text(
                        """
                        UPDATE documents
                        SET doc_metadata = CAST(:metadata AS jsonb)
                        WHERE id = :id
                        """
                    ), {
                        "metadata": metadata_json,
                        "id": new_id
                    })
                    
                    logger.info(f"Inserted case: {title} with ID {new_id}")
                
                import_count += 1
                
                # Commit every 10 cases to avoid long transactions
                if import_count % 10 == 0:
                    conn.commit()
                    logger.info(f"Committed batch of cases - {import_count} processed so far")
            
            # Final commit
            conn.commit()
            
            logger.info(f"Imported/updated {import_count} cases in total")
            return True
    except Exception as e:
        logger.error(f"Error importing cases: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if import_cases():
        logger.info("NSPE case import completed successfully")
        sys.exit(0)
    else:
        logger.error("NSPE case import failed")
        sys.exit(1)
