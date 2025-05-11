#!/usr/bin/env python3
"""
Script to synchronize cases between 'document' and 'documents' tables.
The McLaren analysis script created cases in a 'document' table (singular),
but the web interface is looking for them in the 'documents' table (plural).
"""

import sys
import os
import logging
from sqlalchemy import create_engine, text

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("sync_document_tables")

def sync_tables():
    """
    Synchronize cases between 'document' and 'documents' tables.
    """
    try:
        # Connect with properly formatted URL
        engine = create_engine(
            "postgresql://postgres:PASS@localhost:5433/ai_ethical_dm"
        )
        logger.info("Connecting to database with properly formatted URL")

        with engine.connect() as conn:
            # Check if tables exist
            document_table_exists = conn.execute(text("SELECT to_regclass('public.document')")).fetchone()[0] is not None
            documents_table_exists = conn.execute(text("SELECT to_regclass('public.documents')")).fetchone()[0] is not None
            
            if not document_table_exists:
                logger.error("'document' table does not exist")
                return False
            
            if not documents_table_exists:
                logger.error("'documents' table does not exist")
                return False
            
            # Check for cases in 'document' table
            case_count = conn.execute(text("SELECT COUNT(*) FROM document")).fetchone()[0]
            logger.info(f"Found {case_count} cases in 'document' table")
            
            if case_count == 0:
                logger.warning("No cases found in 'document' table")
                return True
            
            # Get cases from 'document' table
            cases = conn.execute(text("SELECT * FROM document")).fetchall()
            
            # Insert cases into 'documents' table
            insertion_count = 0
            for case in cases:
                # Extract case data
                title = case.title
                content = case.content
                content_type = case.content_type
                metadata = case.metadata
                
                # Check if the case already exists in 'documents' table
                existing = conn.execute(
                    text("SELECT id FROM documents WHERE title = :title"),
                    {"title": title}
                ).fetchone()
                
                if existing:
                    logger.info(f"Case '{title}' already exists in 'documents' table (id: {existing[0]}), skipping")
                    continue
                
                # Insert case into 'documents' table
                try:
                    logger.info(f"Attempting to insert case '{title}' with content length: {len(content) if content else 0}")
                    result = conn.execute(
                        text("""
                            INSERT INTO documents 
                            (title, content, document_type, world_id, doc_metadata, processing_status, processing_progress, created_at, updated_at)
                            VALUES
                            (:title, :content, 'case_study', 1, :metadata, 'completed', 100, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                            RETURNING id
                        """),
                        {"title": title, "content": content, "metadata": metadata}
                    )
                    # Commit after each insert to ensure it's saved
                    conn.commit()
                    new_id = result.fetchone()[0]
                    logger.info(f"Inserted case '{title}' into 'documents' table with ID {new_id}")
                    insertion_count += 1
                except Exception as e:
                    logger.error(f"Error inserting case '{title}': {str(e)}")
            
            # Get principle instantiations and sync them
            try:
                # Check if principle_instantiations table exists
                principle_table_exists = conn.execute(text("SELECT to_regclass('public.principle_instantiations')")).fetchone()[0] is not None
                
                if principle_table_exists:
                    # For each case that was inserted, update related references in principle_instantiations
                    for case in cases:
                        original_id = case.id
                        
                        # Find the new ID in the documents table
                        new_case = conn.execute(
                            text("SELECT id FROM documents WHERE title = :title"),
                            {"title": case.title}
                        ).fetchone()
                        
                        if new_case:
                            new_id = new_case[0]
                            
                            # Copy principle instantiations
                            conn.execute(
                                text("""
                                    INSERT INTO principle_instantiations_documents
                                    (case_id, principle_uri, principle_label, fact_text, fact_context, 
                                    technique_type, confidence, is_negative, created_at, updated_at)
                                    SELECT :new_id, principle_uri, principle_label, fact_text, fact_context,
                                    technique_type, confidence, is_negative, created_at, updated_at
                                    FROM principle_instantiations
                                    WHERE case_id = :old_id
                                """),
                                {"new_id": new_id, "old_id": original_id}
                            )
                            
                            # Copy principle conflicts
                            conn.execute(
                                text("""
                                    INSERT INTO principle_conflicts_documents
                                    (case_id, principle1_uri, principle2_uri, principle1_label, principle2_label,
                                    resolution_type, override_direction, context, created_at, updated_at)
                                    SELECT :new_id, principle1_uri, principle2_uri, principle1_label, principle2_label,
                                    resolution_type, override_direction, context, created_at, updated_at
                                    FROM principle_conflicts
                                    WHERE case_id = :old_id
                                """),
                                {"new_id": new_id, "old_id": original_id}
                            )
            except Exception as e:
                logger.warning(f"Could not sync principle tables: {str(e)}")
                logger.warning("This is expected if the principle_instantiations_documents table doesn't exist")
                
            # Commit changes
            conn.commit()
            
            logger.info(f"Successfully synchronized {insertion_count} cases from 'document' to 'documents' table")
        return True
    except Exception as e:
        logger.error(f"Error synchronizing tables: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    if sync_tables():
        logger.info("Table synchronization completed successfully")
        sys.exit(0)
    else:
        logger.error("Table synchronization failed")
        sys.exit(1)
