#!/usr/bin/env python3
"""
Script to fix the empty case content in the documents table.
"""

import sys
import logging
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("fix_case_content")

def fix_case_content():
    """
    Copy content from document table to documents table for cases
    """
    try:
        # Connect to database
        engine = create_engine(
            "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
        )
        logger.info("Connected to database")

        with engine.connect() as conn:
            # Fetch all cases from document table
            document_cases = conn.execute(text(
                """
                SELECT id, title, content
                FROM document
                """
            )).fetchall()
            
            logger.info(f"Found {len(document_cases)} cases in 'document' table")
            
            # For each case in document table
            fixed_count = 0
            for doc_case in document_cases:
                original_id = doc_case.id
                title = doc_case.title
                content = doc_case.content
                
                if content:
                    logger.info(f"Case {title} (ID: {original_id}) has content length: {len(content)}")
                
                    # Find matching case in documents table
                    target_case = conn.execute(text(
                        """
                        SELECT id, title, document_type
                        FROM documents
                        WHERE title = :title AND document_type = 'case_study'
                        """
                    ), {"title": title}).fetchone()
                    
                    if target_case:
                        logger.info(f"Found matching case in 'documents' table with ID: {target_case.id}")
                        
                        # Update content in documents table
                        conn.execute(text(
                            """
                            UPDATE documents
                            SET content = :content
                            WHERE id = :id
                            """
                        ), {"content": content, "id": target_case.id})
                        
                        fixed_count += 1
                        logger.info(f"Updated content for case '{title}' (ID: {target_case.id})")
                    else:
                        logger.warning(f"No matching case found for '{title}' in 'documents' table")
                else:
                    logger.warning(f"Case '{title}' (ID: {original_id}) has no content to copy")
            
            # Commit changes
            conn.commit()
            
            logger.info(f"Fixed content for {fixed_count} cases")
            return True
    except Exception as e:
        logger.error(f"Error fixing case content: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if fix_case_content():
        logger.info("Case content fix completed successfully")
        sys.exit(0)
    else:
        logger.error("Case content fix failed")
        sys.exit(1)
