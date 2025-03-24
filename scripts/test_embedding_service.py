#!/usr/bin/env python
"""
Test script for the embedding service.
This script tests the basic functionality of the embedding service.
"""

import os
import sys
import logging
from flask import Flask

# Add the parent directory to the path so we can import the app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.document import Document, DocumentChunk
from app.services.embedding_service import EmbeddingService

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_embedding_service():
    """Test the embedding service."""
    app = create_app()
    
    with app.app_context():
        try:
            # Create embedding service
            logger.info("Creating embedding service...")
            embedding_service = EmbeddingService()
            
            # Test embedding generation
            logger.info("Testing embedding generation...")
            test_texts = [
                "This is a test sentence for embedding generation.",
                "Another test sentence with different content.",
                "A third test sentence to ensure the embedding service works correctly."
            ]
            
            embeddings = embedding_service.embed_documents(test_texts)
            logger.info(f"Generated {len(embeddings)} embeddings")
            logger.info(f"Embedding dimension: {len(embeddings[0])}")
            
            # Test similarity search (if there are documents in the database)
            doc_count = Document.query.count()
            chunk_count = DocumentChunk.query.count()
            logger.info(f"Found {doc_count} documents and {chunk_count} chunks in the database")
            
            if chunk_count > 0:
                logger.info("Testing similarity search...")
                query = "ethical guidelines for decision making"
                results = embedding_service.search_similar_chunks(query, k=3)
                logger.info(f"Found {len(results)} similar chunks")
                
                for i, result in enumerate(results):
                    logger.info(f"Result {i+1}:")
                    logger.info(f"  Distance: {result['distance']}")
                    logger.info(f"  Title: {result['title']}")
                    logger.info(f"  Text: {result['chunk_text'][:100]}...")
            else:
                logger.info("Skipping similarity search test as there are no document chunks in the database")
                logger.info("To test similarity search, upload some documents first")
            
            logger.info("Embedding service test completed successfully")
            return True
        
        except Exception as e:
            logger.error(f"Error testing embedding service: {str(e)}")
            return False

def create_test_document():
    """Create a test document in the database."""
    app = create_app()
    
    with app.app_context():
        try:
            # Check if test document already exists
            existing = Document.query.filter_by(title="Test Document").first()
            if existing:
                logger.info("Test document already exists, skipping creation")
                return existing.id
            
            # Create uploads directory if it doesn't exist
            uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'app', 'uploads')
            os.makedirs(uploads_dir, exist_ok=True)
            
            # Create a test text file
            test_file_path = os.path.join(uploads_dir, 'test_document.txt')
            with open(test_file_path, 'w') as f:
                f.write("""
                # Ethical Guidelines for Decision Making
                
                ## Introduction
                
                These guidelines provide a framework for making ethical decisions in complex scenarios.
                
                ## Core Principles
                
                1. **Respect for Autonomy**: Respect individuals' rights to make their own decisions.
                2. **Beneficence**: Act in the best interest of others.
                3. **Non-maleficence**: Do no harm.
                4. **Justice**: Treat all cases fairly and equally.
                
                ## Decision-Making Process
                
                1. Identify the ethical issues involved
                2. Consider the relevant facts
                3. Evaluate alternative actions
                4. Make a decision and justify it
                5. Reflect on the outcome
                
                ## Special Considerations
                
                When dealing with vulnerable populations, additional care must be taken to ensure their interests are protected.
                
                ## Conclusion
                
                Ethical decision-making requires careful consideration of principles, facts, and potential consequences.
                """)
            
            # Create document record
            document = Document(
                title="Test Document",
                document_type="guideline",
                file_path=test_file_path,
                file_type="txt"
            )
            
            db.session.add(document)
            db.session.commit()
            logger.info(f"Created test document with ID {document.id}")
            
            # Process document
            embedding_service = EmbeddingService()
            embedding_service.process_document(document.id)
            logger.info("Processed test document")
            
            return document.id
        
        except Exception as e:
            logger.error(f"Error creating test document: {str(e)}")
            return None

if __name__ == "__main__":
    # Check if we should create a test document
    if len(sys.argv) > 1 and sys.argv[1] == "--create-test":
        logger.info("Creating test document...")
        doc_id = create_test_document()
        if doc_id:
            logger.info(f"Test document created with ID {doc_id}")
        else:
            logger.error("Failed to create test document")
    else:
        # Just test the embedding service
        success = test_embedding_service()
        if success:
            logger.info("All tests passed!")
        else:
            logger.error("Tests failed!")
            sys.exit(1)
