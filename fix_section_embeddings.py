#!/usr/bin/env python3
"""
Fix section embeddings in the database.

This script generates and stores embeddings for document sections with missing
embeddings. It handles both new sections and sections with corrupted embeddings.
"""

import os
import sys
import logging
import argparse
import numpy as np
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ttl_triple_association.embedding_service import EmbeddingService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Fix section embeddings in the database',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument('--document-id', type=int, default=None,
                       help='Specific document ID to process (optional)')
    parser.add_argument('--section-id', type=int, default=None,
                       help='Specific section ID to process (optional)')
    parser.add_argument('--force', action='store_true', default=False,
                       help='Force regeneration of embeddings even if they exist')
    parser.add_argument('--batch-size', type=int, default=10,
                       help='Number of sections to process in each batch')
    parser.add_argument('--db-url', type=str, default=None,
                       help='Database connection URL (defaults to environment variable)')
    parser.add_argument('--model', type=str, default='all-MiniLM-L6-v2',
                       help='Embedding model to use')
    parser.add_argument('--device', type=str, default=None,
                       help='Device to use for embedding generation (None, cpu, cuda)')
    
    return parser.parse_args()

def get_db_url(provided_url=None):
    """Get database URL from arguments or environment variables."""
    return provided_url or os.environ.get(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5433/ai_ethical_dm"
    )

def initialize_embedding_service(model_name, device):
    """Initialize the embedding service."""
    service = EmbeddingService(model_name=model_name, device=device)
    success = service.load_model()
    if not success:
        raise RuntimeError("Failed to load embedding model")
    return service

def check_section_has_embedding(conn, section_id):
    """Check if a section already has a valid embedding."""
    try:
        # Check if the embedding is not null
        query = text("""
            SELECT (embedding IS NOT NULL) as has_embedding
            FROM document_sections
            WHERE id = :section_id
        """)
        
        result = conn.execute(query, {"section_id": section_id})
        row = result.fetchone()
        
        if row:
            return row[0]
        else:
            logger.warning(f"Section {section_id} not found")
            return False
    except Exception as e:
        logger.warning(f"Error checking embedding for section {section_id}: {str(e)}")
        return False

def get_section_content(conn, section_id):
    """Get the content of a section."""
    query = text("""
        SELECT id, section_id, content
        FROM document_sections
        WHERE id = :section_id
    """)
    
    result = conn.execute(query, {"section_id": section_id})
    row = result.fetchone()
    
    if row:
        return {
            "id": row[0],
            "title": row[1] or f"Section {row[0]}",
            "content": row[2]
        }
    else:
        logger.warning(f"Section {section_id} not found")
        return None

def store_section_embedding(conn, section_id, embedding, engine=None):
    """
    Store embedding for a section.
    
    Args:
        conn: Database connection
        section_id: ID of the section
        embedding: Embedding to store (numpy array)
        engine: SQLAlchemy engine for creating new connections if needed
        
    Returns:
        bool: Success status
    """
    try:
        # Convert numpy array to a string representation suitable for pgvector
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"
        
        # Store embedding in document_sections table - using direct string formatting
        # for the vector cast since parameter binding doesn't work well with type casts
        query = text(f"""
            UPDATE document_sections 
            SET embedding = '{embedding_str}'::vector
            WHERE id = :section_id
        """)
        
        conn.execute(query, {"section_id": section_id})
        
        logger.info(f"Successfully stored embedding for section {section_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error storing embedding for section {section_id}: {str(e)}")
        
        # Try alternative storage method if pgvector fails and we have an engine
        if engine is not None:
            try:
                logger.info(f"Attempting alternative storage method for section {section_id}")
                
                # Store as JSON array string without casting to vector
                query = text("""
                    UPDATE document_sections 
                    SET embedding = :embedding
                    WHERE id = :section_id
                """)
                
                # Create a new connection to avoid transaction issues
                with engine.begin() as new_conn:
                    new_conn.execute(query, {
                        "section_id": section_id,
                        "embedding": embedding_str
                    })
                
                logger.info(f"Successfully stored embedding as string for section {section_id}")
                return True
                
            except Exception as e2:
                logger.error(f"Alternative storage method also failed: {str(e2)}")
        else:
            logger.error("Cannot try alternative method without engine")
            
        return False

def process_section(conn, section_id, embedding_service, force=False, engine=None):
    """
    Process a single section: generate and store embedding.
    
    Args:
        conn: Database connection
        section_id: ID of the section to process
        embedding_service: EmbeddingService instance
        force: Whether to force regeneration of existing embeddings
        engine: SQLAlchemy engine for creating new connections if needed
        
    Returns:
        bool: Success status
    """
    try:
        # Check if section already has embedding
        if not force and check_section_has_embedding(conn, section_id):
            logger.info(f"Section {section_id} already has embedding, skipping (use --force to override)")
            return True
        
        # Get section content
        section = get_section_content(conn, section_id)
        if not section:
            return False
        
        # Generate embedding
        content = section["content"]
        if not content:
            logger.warning(f"Section {section_id} has no content, skipping")
            return False
        
        logger.info(f"Generating embedding for section {section_id} ({len(content)} chars)")
        embedding = embedding_service.generate_embedding(content)
        
        if embedding is None:
            logger.error(f"Failed to generate embedding for section {section_id}")
            return False
        
        # Store embedding
        success = store_section_embedding(conn, section_id, embedding, engine)
        
        return success
        
    except Exception as e:
        logger.error(f"Error processing section {section_id}: {str(e)}")
        return False

def get_document_sections(conn, document_id):
    """Get all section IDs for a document."""
    query = text("""
        SELECT id 
        FROM document_sections 
        WHERE document_id = :document_id
        ORDER BY id
    """)
    
    result = conn.execute(query, {"document_id": document_id})
    return [row[0] for row in result]

def process_document(engine, document_id, embedding_service, force=False, batch_size=10):
    """
    Process all sections in a document.
    
    Args:
        engine: SQLAlchemy engine
        document_id: ID of the document to process
        embedding_service: EmbeddingService instance
        force: Whether to force regeneration of existing embeddings
        batch_size: Number of sections to process in each batch
        
    Returns:
        dict: Results with counts
    """
    results = {
        "document_id": document_id,
        "total_sections": 0,
        "processed": 0,
        "successful": 0,
        "failed": 0
    }
    
    try:
        with engine.begin() as conn:
            # Get document title
            query = text("SELECT title FROM documents WHERE id = :document_id")
            result = conn.execute(query, {"document_id": document_id})
            document = result.fetchone()
            
            if not document:
                logger.error(f"Document {document_id} not found")
                return results
            
            document_title = document[0]
            logger.info(f"Processing document {document_id}: {document_title}")
            
            # Get all sections
            sections = get_document_sections(conn, document_id)
            results["total_sections"] = len(sections)
            
            if not sections:
                logger.warning(f"No sections found for document {document_id}")
                return results
                
            logger.info(f"Found {len(sections)} sections for document {document_id}")
            
        # Process sections in batches
        for i in range(0, len(sections), batch_size):
            batch = sections[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1} of {(len(sections) + batch_size - 1)//batch_size}")
            
            for section_id in batch:
                with engine.begin() as conn:
                    success = process_section(conn, section_id, embedding_service, force, engine)
                    
                    results["processed"] += 1
                    if success:
                        results["successful"] += 1
                    else:
                        results["failed"] += 1
                    
                    # Log progress
                    if results["processed"] % 10 == 0 or results["processed"] == results["total_sections"]:
                        logger.info(f"Progress: {results['processed']}/{results['total_sections']} sections processed")
        
        return results
        
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {str(e)}")
        return results

def main():
    """Main entry point."""
    args = parse_args()
    
    # Get database URL
    db_url = get_db_url(args.db_url)
    
    # Initialize database connection
    logger.info(f"Connecting to database...")
    engine = create_engine(db_url)
    
    # Initialize embedding service
    logger.info(f"Initializing embedding service with model: {args.model}")
    embedding_service = initialize_embedding_service(args.model, args.device)
    
    # Process based on provided arguments
    if args.section_id:
        logger.info(f"Processing single section {args.section_id}")
        with engine.begin() as conn:
            success = process_section(conn, args.section_id, embedding_service, args.force, engine)
            
            if success:
                logger.info(f"Successfully processed section {args.section_id}")
            else:
                logger.error(f"Failed to process section {args.section_id}")
                return 1
    
    elif args.document_id:
        logger.info(f"Processing all sections in document {args.document_id}")
        results = process_document(
            engine, 
            args.document_id, 
            embedding_service,
            args.force,
            args.batch_size
        )
        
        logger.info(f"Document processing complete.")
        logger.info(f"Total sections: {results['total_sections']}")
        logger.info(f"Processed: {results['processed']}")
        logger.info(f"Successful: {results['successful']}")
        logger.info(f"Failed: {results['failed']}")
        
        if results['failed'] > 0:
            logger.warning(f"{results['failed']} sections failed processing")
            return 1
    
    else:
        logger.error("Either --section-id or --document-id must be provided")
        return 1
    
    logger.info("Processing complete")
    return 0

if __name__ == "__main__":
    sys.exit(main())
