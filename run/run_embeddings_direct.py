#!/usr/bin/env python
"""
Direct script to update section embeddings for all cases.
Simplified approach that connects to the database and processes all cases.
"""
import os
import sys
import time
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
import psycopg2
import psycopg2.extras

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"direct_embeddings_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
if os.path.exists('.env'):
    load_dotenv()
    logger.info("Loaded environment from .env file")

def get_db_connection():
    """Create a connection to the database."""
    db_url = os.environ.get('DATABASE_URL', 'postgresql://postgres:PASS@localhost:5433/ai_ethical_dm')
    logger.info(f"Connecting to database: {db_url}")
    
    # Parse connection string
    conn_parts = db_url.replace('postgresql://', '').split('/')
    dbname = conn_parts[1]
    user_host_port = conn_parts[0].split('@')
    user_pass = user_host_port[0].split(':')
    user = user_pass[0]
    password = user_pass[1]
    host_port = user_host_port[1].split(':')
    host = host_port[0]
    port = int(host_port[1]) if len(host_port) > 1 else 5432
    
    # Connect to database
    conn = psycopg2.connect(
        dbname=dbname,
        user=user,
        password=password,
        host=host,
        port=port
    )
    logger.info("Database connection established")
    return conn

def find_cases_with_structure(conn):
    """Find all cases that have document structure metadata."""
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        # Find all documents with non-null metadata
        cursor.execute("SELECT id, title, doc_metadata FROM documents WHERE doc_metadata IS NOT NULL")
        rows = cursor.fetchall()
        logger.info(f"Found {len(rows)} documents with metadata")
        
        # Filter documents with document_structure
        case_ids = []
        for row in rows:
            doc_id = row['id']
            metadata = row['doc_metadata'] 
            
            if metadata and isinstance(metadata, dict) and 'document_structure' in metadata:
                case_ids.append(doc_id)
        
        logger.info(f"Found {len(case_ids)} cases with document structure")
        return case_ids
        
    except Exception as e:
        logger.exception(f"Error finding cases with structure: {str(e)}")
        return []
    finally:
        cursor.close()

def get_case_metadata(conn, case_id):
    """Get metadata for a specific case."""
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    
    try:
        cursor.execute("SELECT doc_metadata FROM documents WHERE id = %s", (case_id,))
        row = cursor.fetchone()
        
        if row and row['doc_metadata']:
            return row['doc_metadata']
        else:
            logger.warning(f"No metadata found for case {case_id}")
            return {}
            
    except Exception as e:
        logger.exception(f"Error getting case metadata: {str(e)}")
        return {}
    finally:
        cursor.close()

def update_case_metadata(conn, case_id, metadata):
    """Update metadata for a specific case."""
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "UPDATE documents SET doc_metadata = %s WHERE id = %s",
            (json.dumps(metadata), case_id)
        )
        conn.commit()
        logger.info(f"Updated metadata for case {case_id}")
        return True
        
    except Exception as e:
        conn.rollback()
        logger.exception(f"Error updating case metadata: {str(e)}")
        return False
    finally:
        cursor.close()

def store_section_embedding(conn, document_id, section_id, section_type, content, embedding):
    """Store a section embedding in the document_sections table."""
    cursor = conn.cursor()
    
    try:
        # Check if section already exists
        cursor.execute(
            "SELECT id FROM document_sections WHERE document_id = %s AND section_id = %s",
            (document_id, section_id)
        )
        existing = cursor.fetchone()
        
        if existing:
            # Update existing section
            cursor.execute(
                """
                UPDATE document_sections SET 
                section_type = %s, 
                content = %s, 
                embedding = %s::vector, 
                updated_at = now()
                WHERE document_id = %s AND section_id = %s
                """,
                (section_type, content, embedding, document_id, section_id)
            )
            logger.info(f"Updated existing section {section_id} for document {document_id}")
        else:
            # Create new section
            cursor.execute(
                """
                INSERT INTO document_sections 
                (document_id, section_id, section_type, content, embedding, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s::vector, now(), now())
                """,
                (document_id, section_id, section_type, content, embedding)
            )
            logger.info(f"Created new section {section_id} for document {document_id}")
        
        conn.commit()
        return True
        
    except Exception as e:
        conn.rollback()
        logger.exception(f"Error storing section embedding: {str(e)}")
        return False
    finally:
        cursor.close()

def generate_embedding(text):
    """
    Generate an embedding for the given text.
    This is a placeholder - in a real implementation, we'd call the embedding service.
    For testing, we'll import the actual service if available.
    """
    try:
        from app.services.embedding_service import EmbeddingService
        service = EmbeddingService()
        embedding = service.get_embedding(text)
        logger.info(f"Generated embedding with dimension {len(embedding)}")
        return embedding
    except ImportError:
        logger.warning("Unable to import EmbeddingService, using placeholder")
        # Return a placeholder embedding (384 dimensions of zeros)
        return [0.0] * 384

def process_case(conn, case_id):
    """Process a single case to generate and store section embeddings."""
    logger.info(f"Processing case ID: {case_id}")
    start_time = time.time()
    
    try:
        # Get the document metadata
        metadata = get_case_metadata(conn, case_id)
        
        if not metadata or 'document_structure' not in metadata:
            logger.warning(f"Case {case_id} has no document structure metadata - skipping")
            return False
            
        # Get document structure
        doc_structure = metadata['document_structure']
        
        # Skip if already processed
        if 'section_embeddings' in doc_structure:
            count = doc_structure['section_embeddings'].get('count', 0)
            logger.info(f"Case {case_id} already has {count} section embeddings")
        
        # Get sections
        sections = doc_structure.get('sections', {})
        
        if not sections:
            logger.warning(f"Case {case_id} has no sections - skipping")
            return False
        
        # Process each section
        sections_processed = 0
        for section_id, section_data in sections.items():
            try:
                # Skip if no content
                if 'content' not in section_data or not section_data['content']:
                    logger.warning(f"Section {section_id} has no content - skipping")
                    continue
                
                # Generate embedding
                content = section_data['content']
                section_type = section_data.get('type', section_id)
                embedding = generate_embedding(content)
                
                # Store embedding in document_sections table
                store_section_embedding(
                    conn=conn,
                    document_id=case_id,
                    section_id=section_id,
                    section_type=section_type,
                    content=content,
                    embedding=f"[{','.join(str(x) for x in embedding)}]"
                )
                
                # Update section data with embedding
                section_data['embedding'] = embedding
                sections_processed += 1
                
            except Exception as e:
                logger.exception(f"Error processing section {section_id}: {str(e)}")
        
        # Update metadata
        if sections_processed > 0:
            # Add section_embeddings metadata
            doc_structure['section_embeddings'] = {
                'count': sections_processed,
                'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'storage_type': 'pgvector',
                'embedding_dimension': 384
            }
            
            # Update document metadata
            update_case_metadata(conn, case_id, metadata)
        
        logger.info(f"Successfully processed {sections_processed} sections for case {case_id}")
        logger.info(f"Processing time: {time.time() - start_time:.2f} seconds")
        return True
        
    except Exception as e:
        logger.exception(f"Error processing case {case_id}: {str(e)}")
        return False

def main():
    """Process all cases with document structure."""
    try:
        # Connect to the database
        conn = get_db_connection()
        
        # Find cases with structure
        case_ids = find_cases_with_structure(conn)
        
        if not case_ids:
            logger.warning("No cases found with document structure")
            return
        
        # Skip case 252 (already processed)
        if 252 in case_ids:
            case_ids.remove(252)
            logger.info("Skipping case 252 (already processed)")
        
        # Track progress
        successes = 0
        failures = 0
        
        # Process each case
        for i, case_id in enumerate(case_ids):
            logger.info(f"Processing case {i+1}/{len(case_ids)}: ID {case_id}")
            
            success = process_case(conn, case_id)
            
            if success:
                successes += 1
            else:
                failures += 1
                
            # Add a small delay between cases
            time.sleep(0.5)
        
        logger.info(f"Processing complete: {successes} successes, {failures} failures")
        
    except Exception as e:
        logger.exception(f"Error in main processing: {str(e)}")
    finally:
        # Close the database connection
        if 'conn' in locals() and conn:
            conn.close()
            logger.info("Database connection closed")

if __name__ == "__main__":
    start_time = time.time()
    main()
    elapsed = time.time() - start_time
    logger.info(f"Total execution time: {elapsed:.2f} seconds")
