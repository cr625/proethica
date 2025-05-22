#!/usr/bin/env python3
"""
Generate embeddings for document sections and store them in the database.

This script loads sections from a document, generates embeddings using the
embedding service, and stores them in the database for use by the
section-triple association system.
"""

import os
import sys
import argparse
import logging
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
        description='Generate embeddings for document sections',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument('--document-id', type=int, required=True,
                      help='Document ID to process')
    parser.add_argument('--db-url', type=str, default=None,
                      help='Database connection URL (defaults to environment variable)')
    
    return parser.parse_args()

def generate_embeddings(document_id, db_url=None):
    """
    Generate embeddings for all sections in a document.
    
    Args:
        document_id: ID of the document
        db_url: Database connection URL
    
    Returns:
        Number of sections processed
    """
    # Get database URL
    db_url = db_url or os.environ.get(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5433/ai_ethical_dm"
    )
    
    # Initialize embedding service
    embedding_service = EmbeddingService()
    logger.info(f"Initialized embedding service")
    
    try:
        # Connect to database
        engine = create_engine(db_url)
        
        # Get all sections for the document
        with engine.connect() as conn:
            query = text("""
                SELECT id, content
                FROM document_sections
                WHERE document_id = :document_id
            """)
            
            result = conn.execute(query, {"document_id": document_id})
            sections = [(row[0], row[1]) for row in result]
            
            if not sections:
                logger.warning(f"No sections found for document {document_id}")
                return 0
                
            logger.info(f"Found {len(sections)} sections for document {document_id}")
            
            # Generate and store embeddings
            processed_count = 0
            for section_id, content in sections:
                if not content:
                    logger.warning(f"Section {section_id} has no content, skipping")
                    continue
                
                # Generate embedding
                embedding = embedding_service.generate_embedding(content)
                if embedding is None:
                    logger.warning(f"Failed to generate embedding for section {section_id}")
                    continue
                
                # Convert embedding to bytes for storage
                embedding_bytes = embedding.astype(np.float32).tobytes()
                
                # Update the section with the embedding
                update_query = text("""
                    UPDATE document_sections
                    SET embedding = :embedding
                    WHERE id = :section_id
                """)
                
                conn.execute(update_query, {
                    "section_id": section_id,
                    "embedding": embedding_bytes
                })
                
                processed_count += 1
                logger.info(f"Generated embedding for section {section_id}")
            
            conn.commit()
            logger.info(f"Processed {processed_count} sections for document {document_id}")
            return processed_count
            
    except SQLAlchemyError as e:
        logger.error(f"Database error: {str(e)}")
        return 0
    except Exception as e:
        logger.error(f"Error generating embeddings: {str(e)}")
        return 0

def main():
    """Main entry point."""
    args = parse_args()
    
    try:
        processed = generate_embeddings(args.document_id, args.db_url)
        
        if processed > 0:
            logger.info(f"Successfully generated embeddings for {processed} sections")
            return 0
        else:
            logger.error("Failed to generate embeddings")
            return 1
            
    except Exception as e:
        logger.error(f"Error in embedding generation process: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
