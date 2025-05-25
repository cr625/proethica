#!/usr/bin/env python3
"""
Diagnose section embeddings in the database.

This script helps diagnose issues with section embeddings:
1. Checks database embedding format
2. Verifies embedding types and shapes
3. Tests different embedding retrieval methods
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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Diagnose section embeddings in the database',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    
    parser.add_argument('--document-id', type=int, default=None,
                       help='Specific document ID to diagnose (optional)')
    parser.add_argument('--section-id', type=int, default=None,
                       help='Specific section ID to diagnose (optional)')
    parser.add_argument('--db-url', type=str, default=None,
                       help='Database connection URL (defaults to environment variable)')
    
    return parser.parse_args()

def get_db_url(provided_url=None):
    """Get database URL from arguments or environment variables."""
    return provided_url or os.environ.get(
        "DATABASE_URL", 
        "postgresql://postgres:postgres@localhost:5433/ai_ethical_dm"
    )

def diagnose_section_embedding(engine, section_id):
    """
    Diagnose embedding for a specific section.
    
    Args:
        engine: SQLAlchemy engine
        section_id: ID of the section to diagnose
    """
    try:
        with engine.connect() as conn:
            # Get section metadata
            query = text("""
                SELECT id, section_id, content 
                FROM document_sections
                WHERE id = :section_id
            """)
            
            result = conn.execute(query, {"section_id": section_id})
            section = result.fetchone()
            
            if not section:
                logger.error(f"Section {section_id} not found")
                return
            
            logger.info(f"Section {section_id} metadata:")
            logger.info(f"  - Title: {section[1]}")
            logger.info(f"  - Content length: {len(section[2]) if section[2] else 0} characters")
            
            # Try to get embedding using pg_vector method
            try:
                query = text("""
                    SELECT 
                        embedding,
                        pgvector_to_array(embedding) as array_values, 
                        length(pgvector_to_array(embedding)) as dim_count,
                        pg_column_size(embedding) as bytes_size
                    FROM document_sections
                    WHERE id = :section_id
                """)
                
                result = conn.execute(query, {"section_id": section_id})
                embedding_data = result.fetchone()
                
                if embedding_data and embedding_data[0]:
                    logger.info(f"PGVector embedding information:")
                    logger.info(f"  - Type: {type(embedding_data[0])}")
                    logger.info(f"  - Dimension: {embedding_data[2]}")
                    logger.info(f"  - Size in bytes: {embedding_data[3]}")
                    
                    # Check if we can extract array values
                    if embedding_data[1]:
                        logger.info(f"  - Array values sample: {embedding_data[1][:5]}")
                    else:
                        logger.info(f"  - Unable to extract array values")
                else:
                    logger.warning(f"No PGVector embedding found for section {section_id}")
            except Exception as e:
                logger.error(f"Error retrieving PGVector embedding: {str(e)}")
            
            # Try bytea retrieval method
            try:
                query = text("""
                    SELECT embedding::bytea 
                    FROM document_sections
                    WHERE id = :section_id
                """)
                
                result = conn.execute(query, {"section_id": section_id})
                embedding_bytea = result.fetchone()
                
                if embedding_bytea and embedding_bytea[0]:
                    logger.info(f"Bytea embedding information:")
                    logger.info(f"  - Type: {type(embedding_bytea[0])}")
                    logger.info(f"  - Size in bytes: {len(embedding_bytea[0])}")
                    
                    # Try to convert to numpy array if possible
                    try:
                        embedding_array = np.frombuffer(embedding_bytea[0], dtype=np.float32)
                        logger.info(f"  - Converted to numpy array with shape: {embedding_array.shape}")
                        logger.info(f"  - Sample values: {embedding_array[:5]}")
                    except Exception as e:
                        logger.error(f"  - Failed to convert to numpy array: {str(e)}")
                else:
                    logger.warning(f"No bytea embedding found for section {section_id}")
            except Exception as e:
                logger.error(f"Error retrieving bytea embedding: {str(e)}")
            
            # Try direct casting method
            try:
                query = text("""
                    SELECT embedding::text 
                    FROM document_sections
                    WHERE id = :section_id
                """)
                
                result = conn.execute(query, {"section_id": section_id})
                embedding_text = result.fetchone()
                
                if embedding_text and embedding_text[0]:
                    logger.info(f"Text representation of embedding:")
                    logger.info(f"  - Type: {type(embedding_text[0])}")
                    logger.info(f"  - Length: {len(embedding_text[0])} characters")
                    logger.info(f"  - Sample: {embedding_text[0][:100]}...")
                else:
                    logger.warning(f"No text embedding representation found for section {section_id}")
            except Exception as e:
                logger.error(f"Error retrieving text embedding: {str(e)}")
    
    except SQLAlchemyError as e:
        logger.error(f"Database error while diagnosing section: {str(e)}")
    
def diagnose_document_embeddings(engine, document_id):
    """
    Diagnose embeddings for all sections in a document.
    
    Args:
        engine: SQLAlchemy engine
        document_id: ID of the document to diagnose
    """
    try:
        with engine.connect() as conn:
            # Get document metadata
            query = text("""
                SELECT id, title 
                FROM documents
                WHERE id = :document_id
            """)
            
            result = conn.execute(query, {"document_id": document_id})
            document = result.fetchone()
            
            if not document:
                logger.error(f"Document {document_id} not found")
                return
            
            logger.info(f"Document {document_id}: {document[1]}")
            
            # Get all sections for this document
            query = text("""
                SELECT id 
                FROM document_sections
                WHERE document_id = :document_id
                ORDER BY id
            """)
            
            result = conn.execute(query, {"document_id": document_id})
            sections = [row[0] for row in result]
            
            logger.info(f"Found {len(sections)} sections in document {document_id}")
            
            # Get embedding info for each section
            embedding_stats = {
                "total": len(sections),
                "with_embeddings": 0,
                "without_embeddings": 0,
                "pgvector_format": 0,
                "bytea_format": 0,
                "text_format": 0
            }
            
            for section_id in sections:
                # Check for embeddings
                query = text("""
                    SELECT 
                        (embedding IS NOT NULL) as has_embedding,
                        pg_column_size(embedding) > 0 as has_pgvector,
                        pg_column_size(embedding::bytea) > 0 as has_bytea,
                        length(embedding::text) > 0 as has_text
                    FROM document_sections
                    WHERE id = :section_id
                """)
                
                try:
                    result = conn.execute(query, {"section_id": section_id})
                    stats = result.fetchone()
                    
                    if stats:
                        if stats[0]:  # has_embedding
                            embedding_stats["with_embeddings"] += 1
                            if stats[1]:  # has_pgvector
                                embedding_stats["pgvector_format"] += 1
                            if stats[2]:  # has_bytea
                                embedding_stats["bytea_format"] += 1
                            if stats[3]:  # has_text
                                embedding_stats["text_format"] += 1
                        else:
                            embedding_stats["without_embeddings"] += 1
                except Exception as e:
                    logger.error(f"Error checking embeddings for section {section_id}: {str(e)}")
            
            # Output statistics
            logger.info(f"Embedding statistics for document {document_id}:")
            logger.info(f"  - Total sections: {embedding_stats['total']}")
            logger.info(f"  - Sections with embeddings: {embedding_stats['with_embeddings']}")
            logger.info(f"  - Sections without embeddings: {embedding_stats['without_embeddings']}")
            logger.info(f"  - Sections with pgvector format: {embedding_stats['pgvector_format']}")
            logger.info(f"  - Sections with bytea format: {embedding_stats['bytea_format']}")
            logger.info(f"  - Sections with text format: {embedding_stats['text_format']}")
            
            # Diagnose first section as sample
            if sections:
                logger.info(f"Detailed diagnosis for first section ({sections[0]}):")
                diagnose_section_embedding(engine, sections[0])
    
    except SQLAlchemyError as e:
        logger.error(f"Database error while diagnosing document: {str(e)}")

def main():
    """Main entry point."""
    args = parse_args()
    
    # Get database URL
    db_url = get_db_url(args.db_url)
    
    # Initialize database connection
    logger.info(f"Connecting to database...")
    engine = create_engine(db_url)
    
    # Diagnose based on provided arguments
    if args.section_id:
        logger.info(f"Diagnosing embedding for section {args.section_id}")
        diagnose_section_embedding(engine, args.section_id)
    elif args.document_id:
        logger.info(f"Diagnosing embeddings for document {args.document_id}")
        diagnose_document_embeddings(engine, args.document_id)
    else:
        logger.error("Either --section-id or --document-id must be provided")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
